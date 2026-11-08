"""pytest 公共夹具。

1. 默认把配置指向假服务，快速用例永远不会误用真实 Key 或访问真实网络；
2. ``mock_ai_answer`` 用来替换服务层，让接口测试只关注「服务层之后」的逻辑。
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """快速用例使用假配置；标了 real_api 的用例保留真实 .env 配置。"""
    if "real_api" in request.node.keywords:
        return

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://llm.invalid")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_ai_answer(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """替换 ``app.main.get_ai_answer``，返回一个记录调用入参的列表。

    用法::

        calls = mock_ai_answer(answer="...")
        calls = mock_ai_answer(error=LLMServiceError("boom"))
    """

    def _install(answer: str | None = None, error: Exception | None = None) -> list[str]:
        calls: list[str] = []

        def fake_get_ai_answer(question: str) -> str:
            calls.append(question)
            if error is not None:
                raise error
            return answer if answer is not None else ""

        monkeypatch.setattr("app.main.get_ai_answer", fake_get_ai_answer)
        return calls

    return _install
