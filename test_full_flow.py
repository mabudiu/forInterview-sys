#!/usr/bin/env python3
"""
面试系统完整三阶段流程测试
覆盖: 面试前分析 → 模拟面试 → 面试后复盘
"""
import requests
import time
import json
import sys

BASE = "http://localhost:8000"

# ─── 测试数据 ───────────────────────────────────────────────
JD_TEXT = """
职位: Python后端开发工程师
要求:
1. 熟练掌握 Python/FastAPI/Django
2. 熟悉 PostgreSQL/MySQL/Redis
3. 有 AI/LLM 集成经验优先
4. 3年以上工作经验
5. 熟悉微服务架构、Docker 容器化
"""

RESUME_TEXT = """
姓名: 张三
求职意向: Python后端开发工程师

技能:
- Python, FastAPI, Django, Flask
- PostgreSQL, MySQL, Redis, MongoDB
- Docker, Kubernetes, CI/CD
- OpenAI API, LangChain, RAG
- 微服务架构设计

工作经历:
2021-至今  XX科技公司  Python高级工程师
- 负责后端架构设计与优化
- 基于FastAPI构建AI推理服务
- Docker容器化部署，日均处理10万请求

教育背景:
2017-2021  某重点大学  计算机科学与技术  本科
"""

# ─── 辅助函数 ────────────────────────────────────────────────
def r(method, path, **kw):
    url = f"{BASE}{path}"
    kw.setdefault("timeout", 300)
    resp = requests.request(method, url, **kw)
    print(f"  [{resp.status_code}] {method} {path}")
    if resp.status_code >= 400:
        print(f"  !! ERROR: {resp.text[:200]}")
    return resp


def wait_phase(route, key, interval=3, timeout=120):
    """等待异步任务完成（polling 方式）"""
    start = time.time()
    while time.time() - start < timeout:
        resp = r("GET", route)
        if resp.status_code == 200:
            data = resp.json()
            if key in data and data[key]:
                return data
        print(f"  ...等待 ({int(time.time()-start)}s)")
        time.sleep(interval)
    return None


# ─── 阶段1: 面试前分析 ───────────────────────────────────────
def test_phase1():
    print("\n=== 阶段1: 面试前分析 ===")

    # 上传 JD
    files_jd = {"file": ("jd.txt", JD_TEXT.encode(), "text/plain")}
    r1 = r("POST", "/api/preparation/upload", files=files_jd)
    jd_parsed = r1.json().get("text", "") if r1.status_code == 200 else JD_TEXT
    print(f"  JD解析结果: {len(jd_parsed)} 字")

    # 上传简历
    files_res = {"file": ("resume.txt", RESUME_TEXT.encode(), "text/plain")}
    r2 = r("POST", "/api/preparation/upload", files=files_res)
    resume_parsed = r2.json().get("text", "") if r2.status_code == 200 else RESUME_TEXT
    print(f"  简历解析结果: {len(resume_parsed)} 字")

    # 分析
    payload = {
        "jd_text": jd_parsed,
        "resume_text": resume_parsed,
        "auto_save_resume": True
    }
    resp = r("POST", "/api/preparation/analyze", json=payload)
    if resp.status_code != 200:
        print(f"  分析失败: {resp.text[:200]}")
        return None

    data = resp.json()
    print(f"  匹配度: {data.get('match_score', 'N/A')}")
    print(f"  分析结果Keys: {list(data.keys())}")
    return data


# ─── 阶段2: 模拟面试 ─────────────────────────────────────────
def test_phase2(session_id=None):
    print("\n=== 阶段2: 模拟面试 ===")

    # 使用 /next 接口（前端实际调用）
    payload = {
        "analysis": {"jd_text": JD_TEXT, "resume_text": RESUME_TEXT},
        "history": [],
        "last_question": None,
        "last_answer": None
    }
    resp = r("POST", "/api/interview/next", json=payload)
    if resp.status_code != 200:
        print(f"  启动失败: {resp.text[:200]}")
        return None

    data = resp.json()
    print(f"  done: {data.get('done')}")
    q1 = data.get("question", {})
    q1_text = q1.get("text", "") if isinstance(q1, dict) else q1
    print(f"  第1题: {q1_text[:80]}...")

    if data.get("done"):
        print("  面试直接结束")
        return data

    # 循环回答 (最多5轮)
    history = []
    last_q = q1_text
    max_rounds = 5
    for i in range(max_rounds):
        answer = f"这是第{i+1}轮的测试回答内容，涉及相关技术点和项目细节。"
        history.append({"q": last_q, "a": answer})

        payload = {
            "analysis": {"jd_text": JD_TEXT, "resume_text": RESUME_TEXT},
            "history": history,
            "last_question": last_q,
            "last_answer": answer
        }
        resp = r("POST", "/api/interview/next", json=payload)
        if resp.status_code != 200:
            print(f"  回答失败: {resp.text[:200]}")
            break

        adata = resp.json()
        done = adata.get("done", False)
        next_q = adata.get("question", {})
        next_q_text = next_q.get("text", "") if isinstance(next_q, dict) else next_q
        print(f"  轮次{i+1}: done={done}, 下一题: {next_q_text[:60]}...")

        if done:
            eval_data = adata.get("evaluation", {})
            if eval_data:
                print(f"  综合评分: {eval_data.get('overall_score', 'N/A')}")
                print(f"  评价: {str(eval_data)[:200]}")
            return adata

        last_q = next_q_text

    print(f"  -> 达到{max_rounds}轮，提前结束")
    return {"status": "completed", "rounds": max_rounds}


# ─── 阶段3: 面试后复盘 ────────────────────────────────────────
def test_phase3():
    print("\n=== 阶段3: 面试后复盘 ===")

    # 提交面试问答进行复盘 (自由文本格式)
    raw = """
面试官: 请做一下自我介绍
张三: 我叫张三，有3年Python后端开发经验，主要使用FastAPI和Django框架。

面试官: FastAPI 和 Django 的区别是什么？
张三: FastAPI是轻量级异步框架，自动生成API文档，适合微服务和AI场景；Django是全栈框架，ORM强大，适合管理后台。

面试官: 如何保证接口稳定性？
张三: 通过单元测试、集成测试、CI/CD灰度发布来保证接口稳定性。
    """
    payload = {
        "raw_text": raw,
        "job_title": "Python后端开发工程师"
    }

    resp = r("POST", "/api/review/analyze", json=payload)
    if resp.status_code != 200:
        print(f"  复盘提交失败: {resp.text[:200]}")
        return None

    data = resp.json()
    print(f"  复盘结果Keys: {list(data.keys())}")
    print(f"  自我评分: {data.get('self_score', 'N/A')}")
    improved = data.get("improved_answers", data.get("answers", []))
    print(f"  改进回答数量: {len(improved) if improved else 0}")
    return data


# ─── 主流程 ──────────────────────────────────────────────────
def main():
    print(f"面试系统完整流程测试 @ {BASE}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 健康检查
    r("GET", "/")

    results = {}

    # 阶段1
    p1 = test_phase1()
    results["phase1"] = p1 is not None
    if not p1:
        print("\n!! 阶段1失败，终止")
        return 1

    # 阶段2
    p2 = test_phase2()
    results["phase2"] = p2 is not None
    if not p2:
        print("\n!! 阶段2失败，终止")
        return 1

    # 阶段3
    p3 = test_phase3()
    results["phase3"] = p3 is not None

    # 总结
    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for k, v in results.items():
        status = "✓ PASS" if v else "✗ FAIL"
        print(f"  {k}: {status}")
    print("=" * 50)

    all_pass = all(results.values())
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
