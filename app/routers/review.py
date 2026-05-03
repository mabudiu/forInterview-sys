"""面试复盘路由 — 支持自由格式文本输入"""
import json
import re
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.llm_caller import llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/review", tags=["面试复盘"])


class ReviewRequest(BaseModel):
    raw_text: str
    job_title: Optional[str] = "未知职位"


SYSTEM_REVIEW_PARSE = """你是一位资深面试复盘专家。用户会输入一场真实面试的问答记录（格式自由）。

你的任务是：
1. 解析问答对（问题+回答），忽略编号和格式差异
2. 对整体面试打分（100分制，从技术深度、表达清晰度、逻辑性、项目理解四个维度）
3. 对每个问题从三个维度打分（1-10）：回答完整度、技术深度、逻辑清晰度
4. 给出最佳参考答案（STAR法则：Situation情境、Task任务、Action行动、Result结果）
5. 指出每道题的改进建议

输出格式（严格JSON，不要任何其他内容）：
{
  "overall_score": 整数(0-100),
  "score_breakdown": {
    "技术深度": 整数(0-100),
    "表达清晰度": 整数(0-100),
    "逻辑性": 整数(0-100),
    "项目理解": 整数(0-100)
  },
  "overall_summary": "整体评价，150字以内",
  "strengths": ["亮点1（1-2句话）", "亮点2"],
  "weaknesses": ["不足1（1-2句话）", "不足2"],
  "question_reviews": [
    {
      "question": "问题原文（忠实原句）",
      "dimension_scores": {"完整度": 整数, "技术深度": 整数, "逻辑清晰": 整数},
      "dimension_avg": 浮点数（前三项平均，保留1位小数）,
      "answer_analysis": "对用户回答的详细点评（50字以内），指出哪里好、哪里不足",
      "ideal_answer": "STAR格式参考答案（200字以内）：情境、任务、行动、结果都要有",
      "improvement": "针对这道题的具体改进建议（50字以内）",
      "category": "技术基础/项目经历/场景分析/行为面试/其他"
    }
  ],
  "category_summary": {
    "技术基础": {"avg": 浮点数, "count": 整数, "建议": "该类别整体建议"},
    "项目经历": {"avg": 浮点数, "count": 整数, "建议": "该类别整体建议"},
    "场景分析": {"avg": 浮点数, "count": 整数, "建议": "该类别整体建议"},
    "行为面试": {"avg": 浮点数, "count": 整数, "建议": "该类别整体建议"}
  },
  "improvement_plan": ["优先级最高的下阶段练习计划1", "计划2", "计划3"]
}

注意：
- overall_score 要客观真实，不打高分敷衍
- ideal_answer 必须用STAR法则，情境+任务+行动+结果缺一不可
- question_reviews 的 question 必须是用户实际输入的问题原文
- 只输出JSON"""


def _robust_json(raw_text: str) -> str:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u300c", '"').replace("\u300d", '"')
    text = text.replace("\uff02", '"')
    text = text.replace("『", '"').replace("』", '"')
    text = text.replace("«", '"').replace("»", '"')
    if text.startswith("'"):
        text = text[1:]
    if text.endswith("'"):
        text = text[:-1]
    # 清理控制字符
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


def _fallback_review(raw: str, job_title: str) -> Dict[str, Any]:
    """正则兜底：JSON完全损坏时提取关键字段"""
    result: Dict[str, Any] = {
        "overall_score": 0,
        "score_breakdown": {"技术深度": 0, "表达清晰度": 0, "逻辑性": 0, "项目理解": 0},
        "overall_summary": "分析失败，请重试",
        "strengths": [],
        "weaknesses": ["分析失败，请重新提交"],
        "question_reviews": [],
        "category_summary": {},
        "improvement_plan": ["请重新提交面试记录"]
    }
    m = re.search(r'"overall_score"\s*:\s*(\d+)', raw)
    if m:
        result["overall_score"] = int(m.group(1))
    for label in ["技术深度", "表达清晰度", "逻辑性", "项目理解"]:
        m = re.search(rf'"{label}"\s*:\s*(\d+)', raw)
        if m:
            result["score_breakdown"][label] = int(m.group(1))
    qms = re.findall(r'"question"\s*:\s*"([^"]{5,80})"', raw)
    for q in qms[:10]:
        result["question_reviews"].append({
            "question": q,
            "dimension_scores": {"完整度": 5, "技术深度": 5, "逻辑清晰": 5},
            "dimension_avg": 5.0,
            "answer_analysis": "（未解析成功）",
            "ideal_answer": "（未解析成功）",
            "improvement": "请重新提交",
            "category": "其他"
        })
    return result


@router.post("/analyze")
async def review_interview(req: ReviewRequest):
    """分析自由格式的面试问答记录（真实面试复盘）"""
    if not req.raw_text or not req.raw_text.strip():
        return {"error": "请粘贴面试问答记录"}

    messages = [
        {"role": "system", "content": SYSTEM_REVIEW_PARSE},
        {"role": "user", "content": f"## 职位：{req.job_title}\n\n## 面试问答记录：\n{req.raw_text}"}
    ]

    try:
        raw = llm.chat(messages, temperature=0.3, max_tokens=16384)
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return {
            "error": f"模型调用失败: {str(e)}",
            "overall_score": 0,
            "question_reviews": [],
        }

    text = _robust_json(raw)
    try:
        result = json.loads(text)
        # 补充缺失字段
        if "question_reviews" not in result:
            result["question_reviews"] = []
        if "category_summary" not in result:
            result["category_summary"] = {}
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析失败: {e}，尝试重试")
        # 重试一次
        retry_messages = messages + [
            {"role": "user", "content": "上一轮输出无法解析为JSON，请只输出一个JSON对象，不要任何解释或markdown代码块。"}
        ]
        try:
            raw2 = llm.chat(retry_messages, temperature=0.1, max_tokens=8192)
            text2 = _robust_json(raw2)
            result = json.loads(text2)
            return result
        except Exception:
            logger.error(f"重试也失败，raw={raw[:300]}")
            fallback = _fallback_review(text, req.job_title)
            fallback["raw_note"] = "JSON解析失败，已尝试正则提取"
            return fallback
