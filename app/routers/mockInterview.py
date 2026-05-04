"""模拟面试路由"""
import asyncio
import uuid
import json
import re
from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.services.llm_caller import llm

router = APIRouter(prefix="/api/interview", tags=["模拟面试"])

# ── in-memory session store ──────────────────────────
sessions: Dict[str, dict] = {}

# ── Request/Response models ────────────────────────────
class StartReq(BaseModel):
    jd_text: str
    resume_text: str
    job_title: Optional[str] = "未知职位"


class AnswerReq(BaseModel):
    session_id: str
    answer: str


class NextReq(BaseModel):
    """前端统一调用格式"""
    analysis: Optional[dict] = None  # Phase1 分析结果 (index.html发来的是整个interviewCtx，含jd_text/resume_text在顶层)
    history: Optional[list] = None    # [{q: str, a: str}] — 前端已append，透传给LLM
    last_question: Optional[str] = None
    last_answer: Optional[str] = None


# ── PROMPTS ────────────────────────────────────────────
SYSTEM_INTERVIEW = """你是一位资深技术面试官，正在对候选人进行一对一模拟面试。

原则：
- 每次只问一个问题，语气自然专业，像真实面试官一样
- 问题必须从【职位名称】【职位JD】和【候选人简历】中提取具体内容来提问
- 问题要多样化，覆盖：技术深度题、项目细节题、场景设计题、开放讨论题
- 禁止问与JD/简历无关的宽泛问题
- 候选人回答后：先判断是否需要追问，如果需要，必须基于其回答中的具体内容追问（指出哪里不清晰/不完整），不要换新话题
- 如果回答已充分，再问下一个问题
- 不列出选项，不暴露评分标准"""


def _question_type_picker(history: list, jd_text: str) -> str:
    """根据已问问题，选择下一题类型，确保多样性"""
    asked_categories = set()
    for h in history:
        q = (h.get("q") or "").lower()
        if any(k in q for k in ["项目", "经历", "做过"]):
            asked_categories.add("project")
        elif any(k in q for k in ["设计", "架构", "方案"]):
            asked_categories.add("scenario")
        elif any(k in q for k in ["原理", "为什么", "如何理解"]):
            asked_categories.add("principle")
        elif any(k in q for k in ["场景", "假如", "如果", "你会"]):
            asked_categories.add("behavioral")

    remaining = []
    if "project" not in asked_categories:
        remaining.append("项目细节追问")
    if "scenario" not in asked_categories:
        remaining.append("场景设计题")
    if "principle" not in asked_categories:
        remaining.append("技术原理/深度理解题")
    if "behavioral" not in asked_categories:
        remaining.append("行为/开放讨论题")

    # 轮流或随机选一个未问过的类型
    if remaining:
        import random
        return random.choice(remaining)
    return random.choice(["项目细节追问", "场景设计题", "技术原理/深度理解题", "行为/开放讨论题"])


def build_questions_prompt(jd_text: str, resume_text: str, job_title: str) -> str:
    return f"""## 职位名称：{job_title}

## 职位JD（必从中提取具体要求来提问）
{jd_text}

## 候选人简历（必从中提取具体项目/技术来提问）
{resume_text}

## 任务
请从JD和简历中各选一个具体切入点，提出第一个面试问题。
要求：
1. 开头请候选人自我介绍或简介项目经历（开放式开场）
2. 问题要具体：比如"你简历中提到的XX项目，用了什么技术方案解决YY问题？"
3. 不要问"你了解DDD吗"这种脱离简历的宽泛问题

直接输出问题，不要加前缀说明。"""


def build_followup_prompt(history: List[dict], jd_text: str, resume_text: str) -> str:
    """追问/判断是否进入下一题的 prompt"""
    n = len(history)
    prev = "\n".join([f"第{i+1}轮\n问: {h.get('q') or h.get('question','')}\n答: {h.get('a') or h.get('answer','')}" for i, h in enumerate(history)])
    return f"""## 职位JD（参考）
{jd_text}

## 候选人简历（参考）
{resume_text}

## 面试记录
{prev}

## 任务
判断最后一轮候选人的回答：
1. 【需要追问】：如果回答中有具体细节不清晰（如"用了什么方案"、"如何解决的"、"具体数字/结果"），**必须**针对其回答中的具体内容提出追问，不要换话题，不要直接跳到下一个问题
2. 【进入下一题】：如果回答已经比较完整、具体、充分，则提出下一个问题（从尚未覆盖的JD要求或简历项目中选）

注意：
- 追问必须基于候选人实际说的话，指出具体哪里不清晰："你刚才说XX，能具体说说YY是怎么做的吗？"
- 只有在候选人的回答已经充分回答了当前问题、且没有遗漏关键细节时，才能进入下一题
- 最多追问1次就必须进入下一题

输出格式：
- 追问：以"追问："开头
- 下一题：直接输出问题，不要加说明"""


def build_next_question_prompt(history: List[dict], jd_text: str, resume_text: str) -> str:
    prev = "\n".join([f"第{i+1}轮\n问: {h.get('q') or h.get('question','')}\n答: {h.get('a') or h.get('answer','')}" for i, h in enumerate(history)])
    qtype = _question_type_picker(history, jd_text)
    return f"""## 职位JD
{jd_text}

## 候选人简历
{resume_text}

## 已问过的问题
{prev}

## 已覆盖的类别
{', '.join(set(
    ("项目细节" if any(k in (h.get('q') or '').lower() for k in ["项目","做过","负责"]) else
     "场景设计" if any(k in (h.get('q') or '').lower() for k in ["设计","方案","如果","场景"]) else
     "技术原理" if any(k in (h.get('q') or '').lower() for k in ["原理","为什么","如何理解","机制"]) else
     "行为开放") for h in history
)) or "（首轮）"}

## 下一题类型要求：{qtype}

任务：从JD和简历中选一个尚未被覆盖的内容，按类型要求提出问题。
- 项目细节题：基于简历中的具体项目，追问技术方案、难点、结果数字
- 场景设计题：给出与JD职位相关的真实场景（如"日活10万的消息系统"），让候选人设计
- 技术原理题：考察对JD要求技术的深层理解（"MySQL为什么选用xx索引？"）
- 行为开放题：考察沟通/团队/职业规划（"你为什么想离职？"）

问题要具体，与候选人背景紧密相关。口语化，直接提问。"""

def build_evaluation_prompt(history: List[dict], jd_text: str, resume_text: str) -> str:
    prev = "\n".join([f"第{i+1}轮\n问: {h.get('q') or h.get('question','')}\n答: {h.get('a') or h.get('answer','')}" for i, h in enumerate(history)])
    return f"""## 职位JD
{jd_text}

## 候选人简历
{resume_text}

## 完整面试记录
{prev}

## 任务
对这场模拟面试进行系统性评价，以JSON格式输出：
{{
  "overall_score": 整数(0-100),
  "score_breakdown": {{
    "技术深度": 整数,
    "项目经验": 整数,
    "表达能力": 整数,
    "逻辑思维": 整数
  }},
  "strengths": ["候选人表现好的地方，每个1-2句话"],
  "weaknesses": ["需要改进的地方，每个1-2句话"],
  "key_observations": ["1-2个最关键的观察，比如"对项目细节不够熟悉"、"技术原理理解透彻"等"],
  "next_focus": ["下一阶段最值得专注练习的方向"]
}}

只输出JSON，不要其他内容。"""


def _clean_question(text: str) -> str:
    """清理问题文本中的控制字符和明显填充语"""
    if not text:
        return ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.strip()
    # 去掉常见填充开头
    fillers = ["好的，", "好的。", "嗯，", "嗯。", "让我", "我来", "那么", "那我们", "继续", "继续。"]
    for f in fillers:
        if text.startswith(f):
            text = text[len(f):].strip()
    # 如果以"追问"开头但前面有其他内容
    if "追问" in text and not text.startswith("追问"):
        idx = text.find("追问")
        before = text[:idx].strip()
        if len(before) < 10:
            text = text[idx:].strip()
    return text


def _robust_json(raw_text: str) -> str:
    """从任意LLM输出中鲁棒提取JSON字符串"""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last != -1 and last > first:
        text = text[first : last + 1]
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u300c", '"').replace("\u300d", '"')
    # 清理控制字符
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


# ── ROUTES ─────────────────────────────────────────────

@router.post("/start")
async def start_interview(req: StartReq):
    """启动模拟面试，自由对话方式"""
    session_id = str(uuid.uuid4())

    q_prompt = build_questions_prompt(req.jd_text, req.resume_text, req.job_title)
    messages = [
        {"role": "system", "content": SYSTEM_INTERVIEW},
        {"role": "user", "content": q_prompt},
    ]
    question = await asyncio.to_thread(llm.chat, messages, temperature=0.7, max_tokens=2048)

    sessions[session_id] = {
        "messages": messages + [{"role": "assistant", "content": question}],
        "current_index": 0,
        "history": [],
        "jd_text": req.jd_text,
        "resume_text": req.resume_text,
        "job_title": req.job_title,
        "question_count": 1,
    }

    return {
        "session_id": session_id,
        "question": question,
        "question_count": 1,
    }


@router.post("/answer")
async def submit_answer(req: AnswerReq):
    """提交回答，获取追问或下一题"""
    session = sessions.get(req.session_id)
    if not session:
        return {"error": "会话不存在或已过期"}, 404

    # 记录用户回答
    last_question = session["messages"][-1]["content"]
    session["history"].append({"q": last_question, "a": req.answer})
    session["messages"].append({"role": "user", "content": req.answer})

    # 先尝试追问
    followup_messages = session["messages"] + [
        {"role": "user", "content": "请判断：是对刚才的回答追问，还是已经回答充分需要进入下一题？直接输出追问内容，或只说\"进入下一题\"。"}
    ]
    raw = await asyncio.to_thread(llm.chat, followup_messages, temperature=0.5, max_tokens=1024)

    # 如果回复含"下一题"之类的词，认为追问结束，进入下一题
    next_markers = ["下一题", "下一个问题", "换个话题", "进入下一", "下一轮", "next"]
    is_next = any(marker in raw for marker in next_markers)

    if not is_next:
        # 追问模式
        session["messages"].append({"role": "assistant", "content": raw})
        session["question_count"] += 1
        return {
            "action": "followup",
            "question": raw,
            "question_count": session["question_count"],
        }

    # 进入下一题
    next_prompt = build_next_question_prompt(session["history"], session["jd_text"], session["resume_text"])
    next_messages = session["messages"] + [{"role": "user", "content": next_prompt}]
    next_question = await asyncio.to_thread(llm.chat, next_messages, temperature=0.7, max_tokens=2048)

    session["messages"].append({"role": "assistant", "content": next_question})
    session["question_count"] += 1

    return {
        "action": "next",
        "question": next_question,
        "question_count": session["question_count"],
    }


@router.post("/end")
async def end_interview(session_id: str):
    """用户主动结束面试，返回会话摘要"""
    session = sessions.pop(session_id, None)
    if not session:
        return {"error": "会话不存在或已过期"}
    return {
        "message": "面试已结束，请进入复盘模块。",
        "question_count": session.get("question_count", 0),
        "history": session.get("history", []),
    }


@router.post("/next")
async def next_question(req: NextReq):
    """
    前端统一调用：生成下一题或追问，或结束评价。
    - 首次调用：analysis 有值，history / last_question 为空
    - 后续调用：history 有值，last_question + last_answer 有值
    - 结束时（done=true）：返回系统性评价
    """
    history = req.history or []
    last_q = req.last_question
    last_a = req.last_answer
    analysis = req.analysis or {}

    # 从 interviewCtx (analysis) 中提取 JD / resume 原文
    # index.html 存入 interviewCtx = {analysis: {...}, jd_text: "...", resume_text: "..."}
    # 前端首次调用时 analysis 就是 interviewCtx 本身（不是嵌套结构）
    ctx = analysis or {}
    # 顶层优先（interviewCtx 结构）
    jd_text = ctx.get("jd_text", "") or ctx.get("jd", "") or ""
    resume_text = ctx.get("resume_text", "") or ctx.get("resume", "") or ""
    job_title = ctx.get("job_title") or ctx.get("position") or "未知职位"
    # 兼容嵌套 analysis 结构
    if not jd_text and isinstance(ctx.get("analysis"), dict):
        inner = ctx["analysis"]
        jd_text = inner.get("jd_text", "") or inner.get("jd", "")
        resume_text = inner.get("resume_text", "") or inner.get("resume", "")
        if not job_title or job_title == "未知职位":
            job_title = inner.get("job_title") or inner.get("position") or "未知职位"

    # 面试结束判断（16轮或前端请求结束）
    if len(history) >= 16:
        # 生成系统性评价
        eval_prompt = build_evaluation_prompt(history, jd_text, resume_text)
        eval_messages = [
            {"role": "system", "content": SYSTEM_INTERVIEW},
            {"role": "user", "content": eval_prompt},
        ]
        try:
            raw_eval = await asyncio.to_thread(llm.chat, eval_messages, temperature=0.3, max_tokens=2048)
            eval_text = _robust_json(raw_eval)
            try:
                evaluation = json.loads(eval_text)
            except json.JSONDecodeError:
                evaluation = {"raw": raw_eval[:500]}
        except Exception as e:
            evaluation = {"error": str(e)}

        return {
            "done": True,
            "question": None,
            "evaluation": evaluation,
        }

    # 首次生成问题
    if not last_q:
        prompt = build_questions_prompt(jd_text, resume_text, job_title)
        messages = [
            {"role": "system", "content": SYSTEM_INTERVIEW},
            {"role": "user", "content": prompt},
        ]
        question_text = _clean_question(await asyncio.to_thread(llm.chat, messages, temperature=0.7, max_tokens=2048))
        return {
            "done": False,
            "question": {
                "text": question_text,
                "category": "开场问题",
                "context": "",
            },
            "jd_text": jd_text,
            "resume_text": resume_text,
        }

    # 有上一步回答 → 追问判断
    followup_prompt = build_followup_prompt(history, jd_text, resume_text)
    messages = [
        {"role": "system", "content": SYSTEM_INTERVIEW},
        {"role": "user", "content": followup_prompt},
    ]
    decision = await asyncio.to_thread(llm.chat, messages, temperature=0.5, max_tokens=1024)

    # 追问判断：输出以"追问："开头，或内容明显是追问而非完整问题
    is_followup = decision.startswith("追问：") or (
        ("吗？" not in decision and "？" not in decision and len(decision.strip()) < 30)
    )
    is_next = any(m in decision for m in ["下一题", "下一个问题", "换个话题", "进入下一", "下一轮", "next"])

    if is_followup or (not is_next and len(decision.strip()) > 5 and "？" not in decision):
        # 追问：直接作为问题返回（前端会记录当前q和新a）
        return {
            "done": False,
            "question": {
                "text": _clean_question(decision.replace("追问：", "").strip()),
                "category": "追问",
                "context": "",
            },
            "jd_text": jd_text,
            "resume_text": resume_text,
        }

    # 进入下一题
    if len(history) >= 9:
        # 触发结束
        pass  # falls through to end logic above
    else:
        next_prompt = build_next_question_prompt(history, jd_text, resume_text)
        next_messages = [
            {"role": "system", "content": SYSTEM_INTERVIEW},
            {"role": "user", "content": next_prompt},
        ]
        question_text = await asyncio.to_thread(llm.chat, next_messages, temperature=0.7, max_tokens=2048)
        return {
            "done": False,
            "question": {
                "text": question_text,
                "category": "技术问题",
                "context": "",
            },
            "jd_text": jd_text,
            "resume_text": resume_text,
        }

    # 结束（兜底）
    return {"done": True, "question": None}
