"""Evidence-grounded OpenAI-compatible LLM adapter."""

from __future__ import annotations

import json
import os
import base64
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def configured_llm() -> tuple[str, Any] | tuple[None, None]:
    """Return the configured provider and a callable, without exposing credentials."""
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    provider = "custom"
    if base_url and "minimaxi.com" in base_url:
        provider = "MiniMax"
    if not api_key:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = base_url or "https://api.deepseek.com/chat/completions"
        model = model or os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash"
        provider = "DeepSeek"
    if not api_key:
        api_key = os.getenv("QWEN_API_KEY")
        base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        model = model or "qwen-plus"
        provider = "Qwen"
    if not api_key or not base_url or not model:
        return None, None

    def call(prompt: str, data: dict[str, Any]) -> str:
        payload = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False, default=str)},
            ],
        }
        request = Request(
            base_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise RuntimeError("LLM response did not contain message content")
        return str(content)

    return provider, call


def llm_status() -> dict[str, Any]:
    provider, _ = configured_llm()
    if provider == "DeepSeek":
        model = os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash"
    elif provider == "Qwen":
        model = os.getenv("LLM_MODEL") or "qwen-plus"
    else:
        model = os.getenv("LLM_MODEL")
    return {"enabled": bool(provider), "provider": provider, "model": model, "mode": "evidence_grounded" if provider else "deterministic_fallback"}


def vision_extract(image_path: Path, content_type: str | None = None) -> dict[str, Any] | None:
    """Extract only visible, reviewable text from an image through the configured vision model."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("QWEN_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or "https://api.minimaxi.com/v1/chat/completions"
    model = os.getenv("VISION_MODEL") or os.getenv("LLM_MODEL") or "MiniMax-M2.5"
    if not api_key or not image_path.exists():
        return None
    mime = content_type or "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "请只转录图片中清晰可见的文字，并按原文输出。无法确认的内容标记为[无法确认]，不要推测。"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ]}],
    }
    request = Request(
        base_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        text = result.get("choices", [{}])[0].get("message", {}).get("content")
        if not text:
            return None
        return {"status": "completed", "engine": "MiniMax-M2.5-vision", "text": str(text)[:10000], "confidence": 0.82, "evidence_based": True}
    except Exception:
        return None
