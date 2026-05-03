# Interview System — 项目规划

## 1. 项目概述

- **项目名称**: Interview System
- **类型**: Web全栈应用（Python后端 + 简洁前端）
- **核心功能**: 面试前准备 → 模拟面试 → 面试后复盘
- **目标用户**: 个人使用

## 2. 技术栈

| 层次 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| 前端 | 原生HTML/CSS/JS（无框架依赖） |
| 文件解析 | PyMuPDF（PDF）、python-docx（Word）、Pillow+pytesseract（图片OCR） |
| LLM调用 | MiniMax API（直接HTTP请求） |
| 会话管理 | 内存存储（个人使用，不需数据库） |

## 3. 项目结构

```
interview-system/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置（API Key等）
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── preparation.py    # 面试前准备路由
│   │   ├── mockInterview.py  # 模拟面试路由
│   │   └── review.py         # 复盘路由
│   ├── services/
│   │   ├── __init__.py
│   │   ├── file_parser.py    # 文件解析服务
│   │   ├── llm_caller.py     # MiniMax API 调用
│   │   └── analyzer.py       # JD/简历分析逻辑
│   └── static/
│       ├── index.html       # 主页面
│       ├── styles.css
│       └── app.js            # 前端交互逻辑
├── requirements.txt
└── PLAN.md
```

## 4. 功能模块详解

### 4.1 面试前准备（第一优先级）

**输入**:
- 职位JD: 支持 `.pdf` / `.docx` / `.png` / `.jpg` 文件上传 或 纯文本粘贴
- 个人简历: 同上

**输出**（MiniMax LLM分析）:
1. **匹配度评分** — 100分制，总分 + 各维度分项（技能/经验/教育/潜力）
2. **匹配项目分析** — JD与简历高度吻合的点
3. **不足项目分析** — JD要求但简历中缺失/薄弱的内容（分高/中/低严重程度）
4. **面试知识清单** — 按类别列出需要准备的知识领域（必考/高频/加分）
5. **详细学习大纲** — 每个知识领域下的具体可操作学习路径

### 4.2 模拟面试（第二优先级）

**模式**: 多轮对话流（session + 内存存储）

**问题来源**:
- 职位所需核心能力相关技术问题（3-5个）
- 简历中项目/经历的具体细节追问（2-4个）
- 场景分析题（1-2个）
- 行为面试STAR类问题（1-2个）
- 高频扩展问题（2-3个）

**交互流程**:
1. 启动 → 一次性生成全部问题列表（10-15个）
2. 逐一展示问题，用户输入回答
3. 系统根据回答质量判断：追问（最多2轮）或进入下一题
4. 最后一题后显示"面试结束" → 引导至复盘

### 4.3 面试后复盘（第三优先级）

**输入**: 用户手动粘贴整个面试的问答记录（Q/A格式解析）

**输出**:
- 整体评分（100分制）+ 评语
- 各问题评分（1-10分）+ 分析
- 最佳参考答案（MiniMax生成）
- 亮点 / 不足 / 改进计划
- 按类别（技术/项目/场景/行为）汇总

## 5. MiniMax API

- **Endpoint**: `https://api.minimax.chat/v1/text/chatcompletion_pro`
- **参数**: GroupId, AuthorId via query, Bearer token via header
- **模型**: MiniMax-Text-01
- **温度**: 0.3（分析/复盘）、0.5（生成问题）

## 6. 优先级里程碑

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 项目骨架 + 文件解析 + 基础UI | ✅ |
| Phase 2 | 面试前分析模块（核心LLM调用） | ✅ |
| Phase 3 | 模拟面试模块 | ✅ |
| Phase 4 | 复盘模块 | ✅ |

## 7. 启动方式

```bash
cd interview-system
pip install -r requirements.txt

# 配置环境变量
export MINIMAX_API_KEY="your-api-key"
export MINIMAX_GROUP_ID="your-group-id"

# 启动服务
python -m app.main
# 访问 http://localhost:8000
```
