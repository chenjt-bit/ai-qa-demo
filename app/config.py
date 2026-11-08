"""集中读取与校验运行配置。

把散落在各模块里的 ``os.getenv`` 收拢到一处，好处是：
1. 缺 Key 时能给出明确错误，而不是悄悄发出 ``Bearer None``；
2. 测试可以通过 monkeypatch 环境变量来覆盖配置，不必依赖真实 .env；
3. 被测服务、LLM 裁判、冒烟脚本共用同一份配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（app/ 的上一层）
BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """缺少必要配置或配置非法。"""


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout: float = 30.0

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


def load_env() -> None:
    """加载项目根目录下的 .env（已存在的环境变量不会被覆盖）。"""
    load_dotenv(dotenv_path=BASE_DIR / ".env")


def _read_timeout() -> float:
    raw = os.getenv("DEEPSEEK_TIMEOUT", "30")
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise ConfigError(f"DEEPSEEK_TIMEOUT 必须是数字，当前为 {raw!r}") from exc
    if timeout <= 0:
        raise ConfigError(f"DEEPSEEK_TIMEOUT 必须大于 0，当前为 {timeout}")
    return timeout


def get_settings() -> Settings:
    """读取当前生效的配置；缺少 API Key 时抛 :class:`ConfigError`。"""
    load_env()

    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    # .env.example 里的占位符也算「没配置」，避免用假 Key 去请求真实接口
    if not api_key or api_key.startswith("sk-xxxx") or api_key in {"your-key", "changeme"}:
        raise ConfigError(
            "未配置 DEEPSEEK_API_KEY：请复制 .env.example 为 .env 并填入真实 Key，"
            "或在环境变量中设置 DEEPSEEK_API_KEY"
        )

    return Settings(
        api_key=api_key,
        base_url=(os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip(),
        model=(os.getenv("DEEPSEEK_MODEL") or "deepseek-chat").strip(),
        timeout=_read_timeout(),
    )
