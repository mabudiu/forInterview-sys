"""JD/简历分析服务 — 面试前准备核心逻辑"""
import json
import re
import logging
from typing import Dict, Any, List, Optional

from app.services.llm_caller import llm

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────

SYSTEM_PREPARATION = """你是一位专业面试咨询顾问。你的任务是对【职位JD】和【个人简历】进行深度分析，输出一份完整、结构化的面试准备报告。

必须严格输出JSON，不要输出任何其他内容。"""

USER_PREPARATION = """## 职位JD
{jd_text}

## 个人简历
{resume_text}

严格输出以下JSON，不要任何其他内容：

{{"overall_score":0-100整数,
"score_breakdown":{{"技能匹配":0,"经验匹配":0,"项目匹配":0,"潜力空间":0}},

"matched_items":[
  {{"aspect":"匹配维度","jd_requirement":"JD要求","resume_evidence":"简历证据","analysis":"为何匹配"}},
  {{"aspect":"匹配维度2","jd_requirement":"JD要求2","resume_evidence":"简历证据2","analysis":"为何匹配2"}},
  {{"aspect":"匹配维度3","jd_requirement":"JD要求3","resume_evidence":"简历证据3","analysis":"为何匹配3"}}
],

"gap_items":[
  {{"aspect":"缺失维度","jd_requirement":"JD要求","severity":"high/medium/low","gap_description":"具体差距","suggestion":"补充建议"}},
  {{"aspect":"缺失维度2","jd_requirement":"JD要求2","severity":"high/medium/low","gap_description":"具体差距2","suggestion":"补充建议2"}},
  {{"aspect":"缺失维度3","jd_requirement":"JD要求3","severity":"high/medium/low","gap_description":"具体差距3","suggestion":"补充建议3"}}
],

"knowledge_areas":[
  {{"category":"知识领域","priority":"必考/高频/了解","topics":["知识点1","知识点2","知识点3","知识点4"]}},
  {{"category":"知识领域2","priority":"必考/高频/了解","topics":["知识点1","知识点2","知识点3","知识点4"]}},
  {{"category":"知识领域3","priority":"必考/高频/了解","topics":["知识点1","知识点2","知识点3","知识点4"]}}
],

"interview_focus":["面试高频问题1","面试高频问题2","面试高频问题3"],

"tips":["面试技巧1","面试技巧2"]
}}

规则：matched_items最多3项、gap_items最多3项、knowledge_areas最多3个，每领域4个知识点。只输出JSON。"""


RETRY_PROMPT = """上一轮的输出无法被解析为JSON。请重新输出，只输出一个合法的JSON对象，不要包含任何解释文字、markdown代码块、或任何其他内容。

要求：
- 只输出JSON，以{{开头，以}}结尾
- 不使用中文引号""
- 不使用markdown代码块标记
- 所有字符串必须用ASCII双引号包围
- 不要有多余的换行和空格

直接输出JSON："""


# ─────────────────────────────────────────────
# JSON 解析（带重试）
# ─────────────────────────────────────────────

def _robust_json(raw_text: str) -> str:
    """从任意LLM输出中鲁棒提取JSON字符串"""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]
    # 替换各种引号变体
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u300c", '"').replace("\u300d", '"')
    text = text.replace("\uff02", '"')
    text = text.replace("『", '"').replace("』", '"')
    text = text.replace("«", '"').replace("»", '"')
    if text.startswith("'"):
        text = text[1:]
    if text.endswith("'"):
        text = text[:-1]
    # 清理控制字符（\x00-\x08 等，JSON不允许但LLM常输出）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


def _normalize_keys(obj):
    """统一字段名格式"""
    if isinstance(obj, dict):
        return {to_snake(k): _normalize_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    return obj


def to_snake(s: str) -> str:
    s = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), s)
    return re.sub(r"[\s\-]+", "_", s).strip("_")


def _fallback_parse(text: str) -> Optional[Dict[str, Any]]:
    """正则兜底：JSON完全损坏时，尝试逐字段提取"""
    result: Dict[str, Any] = {}

    m = re.search(r'"overall_score"\s*:\s*(\d+)', text)
    if m:
        result["overall_score"] = int(m.group(1))

    breakdown = {}
    for label in ["技能匹配", "经验匹配", "教育匹配", "潜力空间"]:
        m = re.search(rf'"{re.escape(label)}"\s*:\s*(\d+)', text)
        if m:
            breakdown[label] = int(m.group(1))
    if breakdown:
        result["score_breakdown"] = breakdown

    # matched_items
    matched = []
    for m in re.finditer(r'"aspect"\s*:\s*"([^"]+)"', text):
        item = {"aspect": m.group(1)}
        seg = text[m.start():m.start() + 500]
        for k, key in [("jd_requirement", "jd_requirement"), ("resume_evidence", "resume_evidence"), ("analysis", "analysis")]:
            km = re.search(rf'"{k}"\s*:\s*"([^"]*)"', seg)
            if km:
                item[key] = km.group(1)
        if item.get("aspect"):
            matched.append(item)
    if matched:
        result["matched_items"] = matched[:5]

    # knowledge_areas — 找所有 category
    knowledge = []
    for m in re.finditer(r'"category"\s*:\s*"([^"]+)"', text):
        seg = text[m.start():m.start() + 300]
        cat = m.group(1)
        pri_m = re.search(r'"priority"\s*:\s*"([^"]+)"', seg)
        top_m = re.search(r'"topics"\s*:\s*\[(.*?)\]', seg, re.DOTALL)
        topics = []
        if top_m:
            topics = re.findall(r'"([^"]+)"', top_m.group(1))
        knowledge.append({"category": cat, "priority": pri_m.group(1) if pri_m else "高频", "topics": topics})
    if knowledge:
        result["knowledge_areas"] = knowledge[:5]

    # tips / interview_focus
    for field in ["tips", "interview_focus"]:
        fm = re.findall(rf'"{field}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if fm:
            items = re.findall(r'"([^"]+)"', fm[0])
            if items:
                result[field] = items

    return result if result else None


def _parse_with_retry(raw: str, messages: List[Dict], max_retries: int = 2) -> Dict[str, Any]:
    """
    尝试解析 LLM 输出为 JSON，失败则自动重试。
    """
    for attempt in range(max_retries + 1):
        text = _robust_json(raw)
        try:
            data = json.loads(text)
            return _normalize_keys(data)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败（尝试 {attempt + 1}/{max_retries + 1}）: {e}")
            if attempt < max_retries:
                # 重试：用更严格的 prompt 要求纯 JSON
                retry_messages = messages + [{"role": "user", "content": RETRY_PROMPT}]
                raw = llm.chat(retry_messages, temperature=0.1, max_tokens=16384)
            else:
                # 终极兜底：正则提取
                fallback = _fallback_parse(text)
                if fallback:
                    return fallback
                return {
                    "error": f"JSON解析失败（已重试{attempt + 1}次）: {e}",
                    "raw_response": raw,
                    "overall_score": 0,
                }


# ─────────────────────────────────────────────
# ANALYZER
# ─────────────────────────────────────────────

def analyze_preparation(jd_text: str, resume_text: str) -> Dict[str, Any]:
    """
    入口：输入JD文本和简历文本，返回分析结果字典
    """
    user_prompt = USER_PREPARATION.format(jd_text=jd_text, resume_text=resume_text)
    messages = [
        {"role": "system", "content": SYSTEM_PREPARATION},
        {"role": "user", "content": user_prompt},
    ]

    logger.info("开始调用 MiniMax 分析 JD 和简历...")
    raw = llm.chat(messages, temperature=0.3, max_tokens=2048)
    logger.info(f"MiniMax 原始返回（前500字符）: {raw[:500]}")

    return _parse_with_retry(raw, messages)
