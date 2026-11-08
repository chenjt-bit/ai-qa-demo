"""服务层单测：不联网、不花钱，直接替换 ``requests.post``。

Mock 层的价值在这里——它验证的是「请求怎么构造、响应怎么解析、异常怎么翻译」，
这些逻辑以前完全裸奔，只有真实 API 用例才碰得到。
"""

from __future__ import annotations

import allure
import pytest
import requests

from app.config import ConfigError
from app.llm_service import LLMServiceError, get_ai_answer
from app.policy import SYSTEM_PROMPT


class FakeResponse:
    def __init__(
        self,
        payload: object = None,
        status_code: int = 200,
        bad_json: bool = False,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self._bad_json = bad_json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> object:
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


def _chat_payload(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


@pytest.fixture
def install_post(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict] = []

    def _install(response: FakeResponse) -> list[dict]:
        def fake_post(url, headers=None, json=None, timeout=None):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
            return response

        monkeypatch.setattr("app.llm_service.requests.post", fake_post)
        return calls

    return _install


@allure.feature("模型服务层")
@allure.story("请求构造")
def test_request_is_built_as_expected(install_post) -> None:
    calls = install_post(FakeResponse(_chat_payload("  您好，生鲜不能退。  ")))

    answer = get_ai_answer("生鲜能退吗？")

    assert answer == "您好，生鲜不能退。", "首尾空白应被去掉"
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://llm.invalid/chat/completions"
    assert call["headers"] == {"Authorization": "Bearer test-key"}
    assert call["json"]["model"] == "test-model"
    assert call["json"]["temperature"] == 0, "被测服务必须可复现"
    assert call["json"]["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert call["json"]["messages"][1] == {"role": "user", "content": "生鲜能退吗？"}


@allure.feature("模型服务层")
@allure.story("上游非 200 必须抛错")
def test_http_error_raises_service_error(install_post) -> None:
    install_post(FakeResponse(status_code=500))

    with pytest.raises(LLMServiceError, match="调用模型失败"):
        get_ai_answer("生鲜能退吗？")


@allure.feature("模型服务层")
@allure.story("响应不是 JSON 必须抛错")
def test_invalid_json_raises_service_error(install_post) -> None:
    install_post(FakeResponse(bad_json=True))

    with pytest.raises(LLMServiceError, match="响应结构异常"):
        get_ai_answer("生鲜能退吗？")


@allure.feature("模型服务层")
@allure.story("响应缺字段必须抛错")
def test_missing_choices_raises_service_error(install_post) -> None:
    install_post(FakeResponse({"error": {"message": "rate limited"}}))

    with pytest.raises(LLMServiceError, match="响应结构异常"):
        get_ai_answer("生鲜能退吗？")


@allure.feature("模型服务层")
@allure.story("空回答必须抛错")
def test_blank_content_raises_service_error(install_post) -> None:
    install_post(FakeResponse(_chat_payload("   ")))

    with pytest.raises(LLMServiceError, match="空回答"):
        get_ai_answer("生鲜能退吗？")


@allure.feature("模型服务层")
@allure.story("缺少 Key 时不发请求")
def test_missing_api_key_raises_config_error(
    install_post, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = install_post(FakeResponse(_chat_payload("不应该被调用")))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    with pytest.raises(ConfigError, match="DEEPSEEK_API_KEY"):
        get_ai_answer("生鲜能退吗？")

    assert calls == [], "缺少 Key 时不应发出真实请求"
