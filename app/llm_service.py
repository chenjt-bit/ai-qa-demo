"""与 DeepSeek 通信的服务层：只负责「把问题发出去、把回答取回来」。

约定：任何上游异常都转成 :class:`LLMServiceError` 抛出，由接口层翻译成 HTTP 状态码。
这样「模型挂了」不会被包装成一条正常回答——否则测试拿不到禁用词，就会假绿。
"""

from __future__ import annotations

from typing import Any

import requests

from app.config import get_settings
from app.policy import SYSTEM_PROMPT


class LLMServiceError(RuntimeError):
    """调用大模型失败：网络、鉴权、超时、响应结构异常等。"""


def build_payload(question: str, model: str) -> dict[str, Any]:
    """构造请求体。

    ``temperature`` 固定为 0：被测服务的行为要尽量可复现，否则断言会随机红绿。
    """
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0,
    }


def get_ai_answer(question: str) -> str:
    """向大模型提问并返回回答文本；失败时抛 :class:`LLMServiceError`。"""
    settings = get_settings()

    try:
        resp = requests.post(
            settings.chat_completions_url,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            json=build_payload(question, settings.model),
            timeout=settings.timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    except requests.RequestException as exc:
        raise LLMServiceError(f"调用模型失败：{exc}") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMServiceError(f"模型响应结构异常：{exc!r}") from exc

    if not isinstance(content, str) or not content.strip():
        raise LLMServiceError("模型返回了空回答")
    return content.strip()
