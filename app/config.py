import os
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件到环境变量

# MiniMax API 配置 (Anthropic 兼容端点)
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "your-api-key-here")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "your-group-id-here")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL_NAME = "MiniMax-M2.7"

# 服务器配置
HOST = "0.0.0.0"
PORT = 8000
