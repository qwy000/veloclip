"""DeepSeek 大模型 API 封装。"""
from __future__ import annotations

import os
from typing import Literal

import httpx

Role = Literal["system", "user", "assistant"]

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
PLACEHOLDER_KEYS = {"sk-your-key-here", "your-api-key", "changeme"}


def _api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key or key in PLACEHOLDER_KEYS:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在 backend/.env 或环境变量中设置。")
    return key


def _is_reasoning_model(model: str) -> bool:
    name = model.lower()
    return "reasoner" in name or "v4-pro" in name or "r1" in name


def _extract_message_text(message: dict) -> str:
    """解析 assistant 回复；思考模型可能仅填充 reasoning_content。"""
    content = (message.get("content") or "").strip()
    if content:
        return content
    reasoning = (message.get("reasoning_content") or "").strip()
    if reasoning:
        return reasoning
    return ""


def _parse_api_error(status: int, body: str) -> str:
    try:
        data = __import__("json").loads(body)
        err = data.get("error") or {}
        msg = err.get("message") or data.get("message") or body[:200]
        code = err.get("code") or err.get("type") or ""
        if code:
            return f"DeepSeek API 错误 ({status}, {code}): {msg}"
        return f"DeepSeek API 错误 ({status}): {msg}"
    except Exception:
        return f"DeepSeek API 错误 ({status}): {body[:200]}"


def _base_url() -> str:
    return os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """调用 DeepSeek Chat Completions API，返回 assistant 文本。"""
    model_name = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    # 思考模型会先消耗 token 做推理，需保证足够输出额度（见 DeepSeek 文档 reasoning_content）
    token_budget = max_tokens
    if _is_reasoning_model(model_name):
        token_budget = max(max_tokens, 8192)

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": token_budget,
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{_base_url()}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code >= 400:
            raise RuntimeError(_parse_api_error(resp.status_code, resp.text))
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek API 返回空 choices")
    message = choices[0].get("message") or {}
    content = _extract_message_text(message)
    if not content:
        reason = choices[0].get("finish_reason") or "unknown"
        raise RuntimeError(
            f"DeepSeek 未返回有效正文（model={model_name}, finish_reason={reason}）。"
            "若使用 deepseek-v4-pro / reasoner，可改用 deepseek-chat 或 deepseek-v4-flash。"
        )
    return content
