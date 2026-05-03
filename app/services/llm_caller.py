"""MiniMax API 调用封装 — Anthropic 兼容端点 + MiniMax-M2.7"""
import json
import logging
from typing import List, Dict, Any

import httpx

from app.config import MINIMAX_API_KEY, ANTHROPIC_BASE_URL, MODEL_NAME

logger = logging.getLogger(__name__)


class MiniMaxCaller:
    def __init__(self, api_key: str = MINIMAX_API_KEY):
        self.api_key = api_key
        self.url = f"{ANTHROPIC_BASE_URL}/v1/messages"

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = MODEL_NAME,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        if not self.api_key or self.api_key == "your-api-key-here":
            raise RuntimeError("MINIMAX_API_KEY 未配置，请在 .env 或系统环境中设置")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        # Anthropic 兼容格式：直接使用 role + content
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        logger.info(f"MiniMax 请求: model={model}, messages={len(messages)}, url={self.url}")

        with httpx.Client(timeout=300.0) as client:
            resp = client.post(self.url, headers=headers, json=payload)

        logger.info(f"MiniMax HTTP {resp.status_code}")

        if resp.status_code != 200:
            logger.error(f"MiniMax 错误: {resp.text[:500]}")
            resp.raise_for_status()

        data = resp.json()

        # Anthropic 兼容响应格式：遍历所有 content 块，收集所有 text
        if "content" in data:
            text_parts = []
            for block in data["content"]:
                if block.get("type") == "text":
                    text_parts.append(block["text"])
            if text_parts:
                text = "\n".join(text_parts)
                logger.info(f"MiniMax 返回长度: {len(text)}")
                return text

        # 兜底旧格式
        reply = data.get("reply", "")
        if reply:
            return reply

        logger.error(f"MiniMax 空响应: {json.dumps(data)[:300]}")
        raise RuntimeError(f"MiniMax API 返回空内容。响应: {json.dumps(data)[:200]}")


# 全局单例
llm = MiniMaxCaller()
