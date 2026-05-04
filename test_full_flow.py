#!/usr/bin/env python3
"""
完整三阶段流程测试脚本 — Interview System
测试: Phase 1 (上传+分析) → Phase 2 (模拟面试) → Phase 3 (复盘)

运行方式:
    cd /Users/apple/interview-system
    python test_full_flow.py

要求: .env 已配置 MINIMAX_API_KEY, 服务器已启动 (uvicorn app.main:app)
"""

import urllib.request
import urllib.error
import json
import time
import sys

BASE = "http://localhost:8000"
TIMEOUT_LLM = 180  # LLM 调用超时秒数
TIMEOUT_SHORT = 15


def api_post(path: str, data: dict, timeout: int = TIMEOUT_LLM) -> dict:
    """发送 JSON POST 请求"""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def phase1_upload_and_analyze():
    """Phase 1: 上传简历+JD → 分析"""
    print("\n" + "=" * 60)
    print("Phase 1: 面试前准备分析")
    print("=" * 60)

    # Step 1: 上传简历文件（text）
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    resume_content = (
        "张三 | 3年Python后端开发经验\n"
        "熟悉: FastAPI, Django, MySQL, Redis, Docker, Git\n"
        "项目1: 电商订单系统（FastAPI + MySQL + Redis）\n"
        "  - 负责订单模块设计与实现，日订单处理10万+\n"
        "  - 优化数据库查询，响应时间从800ms降至50ms\n"
        "项目2: 用户中心服务（微服务架构）\n"
        "  - 独立负责用户认证、权限管理模块\n"
        "  - 使用Redis实现分布式Session\n"
        "期望职位: Python后端开发工程师"
    ).encode("utf-8")

    body = (
        b"--" + boundary.encode() + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="resume.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n" + resume_content + b"\r\n"
        b"--" + boundary.encode() + b"--\r\n"
    )
    req = urllib.request.Request(
        BASE + "/api/preparation/upload",
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SHORT) as r:
        resume_data = json.loads(r.read())
    print(f"  [上传] 简历解析完成: {resume_data['filename']}, {len(resume_data['text'])} 字")

    # Step 2: 分析
    jd_text = (
        "Python后端开发工程师\n"
        "要求:\n"
        "1. 3年以上Python开发经验\n"
        "2. 熟悉FastAPI或Django，有实际项目经验\n"
        "3. 熟悉MySQL/Redis，了解数据库优化\n"
        "4. 了解微服务架构，有Docker使用经验\n"
        "5. 良好的代码风格和团队协作能力"
    )

    print(f"  [分析] 发送请求 (简历 {len(resume_data['text'])} 字, JD {len(jd_text)} 字)...")
    t0 = time.time()
    result = api_post(
        "/api/preparation/analyze",
        {"jd_text": jd_text, "resume_text": resume_data["text"], "auto_save_resume": False},
    )
    elapsed = time.time() - t0
    print(f"  [分析] 完成，耗时 {elapsed:.1f}s")

    score = result.get("overall_score", 0)
    matched = result.get("matched_items", [])
    gaps = result.get("gap_items", [])
    knowledge = result.get("knowledge_areas", [])

    print(f"  [评分] {score}/100")
    print(f"  [匹配项] {matched[:3]}")
    print(f"  [不足项] {gaps[:3]}")
    print(f"  [知识领域] {knowledge[:3]}")

    # 验证字段
    assert isinstance(score, int) and 0 <= score <= 100, f"评分异常: {score}"
    assert isinstance(matched, list), "matched_items 应为列表"
    assert isinstance(gaps, list), "gap_items 应为列表"
    print("  [✓] Phase 1 验证通过")
    return result, jd_text, resume_data["text"]


def phase2_mock_interview(analysis: dict, jd_text: str, resume_text: str):
    """Phase 2: 模拟面试 — 完成3轮问答"""
    print("\n" + "=" * 60)
    print("Phase 2: 模拟面试")
    print("=" * 60)

    interviewCtx = {
        "analysis": analysis,
        "jd_text": jd_text,
        "resume_text": resume_text,
    }

    history = []
    num_rounds = 3

    for round_i in range(1, num_rounds + 1):
        # 构造请求：除了第一轮，每轮都要带 history + 上轮问答
        if round_i == 1:
            payload = {
                "analysis": interviewCtx,
                "history": [],
                "last_question": None,
                "last_answer": None,
            }
        else:
            payload = {
                "analysis": interviewCtx,
                "history": history,
                "last_question": prev_question,
                "last_answer": prev_answer,
            }

        print(f"  [第{round_i}轮] 请求下一题...")
        t0 = time.time()
        data = api_post("/api/interview/next", payload)
        elapsed = time.time() - t0
        print(f"  [第{round_i}轮] 耗时 {elapsed:.1f}s")

        if data.get("done"):
            print(f"  [!] 面试意外结束 (done=True)")
            break

        q = data.get("question", {})
        question_text = q.get("text", "")
        print(f"  [Q{round_i}] {question_text[:80]}...")
        assert question_text, f"问题为空"

        # 模拟回答
        answers = [
            "我主要负责订单模块，使用FastAPI构建RESTful接口，MySQL做持久化，Redis做缓存。"
            "在项目中我优化了慢查询，通过添加复合索引和EXPLAIN分析，将查询时间从800ms降到50ms。",
            "用户认证模块使用JWT token，配合Redis存储黑名单实现主动失效。"
            "权限控制基于RBAC模型，设计了用户-角色-权限三层结构。",
            "使用Docker容器化部署，通过Docker Compose编排多容器，服务横向扩展。"
            "还使用过Nginx做反向代理和负载均衡。",
        ]
        answer_text = answers[round_i - 1]
        print(f"  [A{round_i}] {answer_text[:60]}...")

        history.append({"q": question_text, "a": answer_text})
        prev_question = question_text
        prev_answer = answer_text

    # 主动结束面试（发 done 请求）
    print("  [结束] 发送结束信号...")
    t0 = time.time()
    end_payload = {
        "analysis": interviewCtx,
        "history": history,
        "last_question": prev_question,
        "last_answer": prev_answer,
    }
    # 模拟超过10轮限制触发结束（传10条历史）
    for _ in range(10 - len(history)):
        history.append({"q": "额外问题", "a": "额外回答"})
    end_data = api_post("/api/interview/next", end_payload)
    elapsed = time.time() - t0
    print(f"  [结束] 耗时 {elapsed:.1f}s")

    if end_data.get("done"):
        ev = end_data.get("evaluation", {})
        print(f"  [评估] 完成: score={ev.get('overall_score', 'N/A')}")
        print(f"  [评估] 优点: {ev.get('strengths', [])[:2]}")
        print(f"  [评估] 建议: {ev.get('weaknesses', [])[:2]}")
    else:
        print(f"  [!] 结束信号未返回 done=True")

    print("  [✓] Phase 2 验证通过")
    return end_data.get("evaluation", {})


def phase3_review():
    """Phase 3: 复盘 — 输入面试问答，获得评价"""
    print("\n" + "=" * 60)
    print("Phase 3: 面试后复盘")
    print("=" * 60)

    raw_text = """
面试官: 请介绍一下你在电商订单系统中的具体工作。
候选人: 我负责订单模块设计与实现，使用FastAPI构建RESTful接口，MySQL做持久化，Redis做缓存。日订单处理量在10万以上。
面试官: 如何优化的查询性能？
候选人: 我通过添加复合索引和EXPLAIN分析慢查询，将查询时间从800ms降到50ms。
面试官: Redis在项目中怎么用的？
候选人: 用Redis存储热点数据和分布式锁，实现订单号生成器的高并发支持。
面试官: 微服务架构下如何保证服务间通信的可靠性？
候选人: 使用HTTP+JSON通信，配合超时重试和熔断器（Sentinel）处理故障传递。
"""

    print(f"  [复盘] 提交 {len(raw_text)} 字问答记录...")
    t0 = time.time()
    result = api_post("/api/review/analyze", {"raw_text": raw_text})
    elapsed = time.time() - t0
    print(f"  [复盘] 完成，耗时 {elapsed:.1f}s")

    score = result.get("overall_score", 0)
    reviews = result.get("question_reviews", [])
    summary = result.get("category_summary", {})

    print(f"  [评分] {score}/100")
    print(f"  [问题数] {len(reviews)}")
    if reviews:
        first = reviews[0]
        print(f"  [第1题] Q: {first.get('original_question', '')[:50]}...")
        print(f"        理想答: {first.get('ideal_answer', '')[:60]}...")
        print(f"        改进: {first.get('improvement_points', [])[:2]}")

    assert isinstance(score, int) and 0 <= score <= 100, f"评分异常: {score}"
    assert isinstance(reviews, list), "question_reviews 应为列表"
    print("  [✓] Phase 3 验证通过")
    return result


def main():
    print("Interview System — 完整流程测试")
    print(f"目标服务器: {BASE}")

    # 检查服务器
    try:
        with urllib.request.urlopen(BASE + "/", timeout=5) as r:
            print(f"服务器状态: {r.status}\n")
    except Exception as e:
        print(f"错误: 无法连接服务器 {BASE}: {e}")
        sys.exit(1)

    try:
        p1_result, jd_text, resume_text = phase1_upload_and_analyze()
        p2_evaluation = phase2_mock_interview(p1_result, jd_text, resume_text)
        p3_result = phase3_review()

        print("\n" + "=" * 60)
        print("全部流程测试完成!")
        print(f"  Phase 1 score: {p1_result['overall_score']}")
        print(f"  Phase 2 evaluation: {p2_evaluation.get('overall_score', 'N/A')}")
        print(f"  Phase 3 score: {p3_result['overall_score']}")
        print("=" * 60)
        print("状态: SUCCESS")
    except AssertionError as e:
        print(f"\n断言失败: {e}")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"\nHTTP错误 {e.code}: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"\n异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
