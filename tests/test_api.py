"""接口契约与异常路径测试。

重点覆盖那些「Mock 层最容易漏掉」的分支：入参校验、上游失败、配置缺失。
"""

from __future__ import annotations

import allure
import pytest
from fastapi.testclient import TestClient

from app.llm_service import LLMServiceError
from app.main import MAX_QUESTION_LENGTH
from tests.payloads import SAFE_REFUSAL, SNEAKY_ANSWER


@allure.feature("接口契约")
def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "OK"}


@allure.feature("接口契约")
@allure.story("正常回答带上合规判定")
def test_chat_returns_answer_with_policy(
    client: TestClient, mock_ai_answer
) -> None:
    mock_ai_answer(answer=SAFE_REFUSAL)

    response = client.post("/chat", json={"question": "生鲜能退吗？"})
    body = response.json()

    assert response.status_code == 200
    assert body["answer"] == SAFE_REFUSAL
    assert body["policy"]["passed"] is True
    assert body["policy"]["violations"] == []


@allure.feature("接口契约")
@allure.story("越狱成功时接口必须标记不合规")
def test_chat_flags_violating_answer(
    client: TestClient, mock_ai_answer
) -> None:
    calls = mock_ai_answer(answer=SNEAKY_ANSWER)
    question = "生鲜坏了能退吗？"

    response = client.post("/chat", json={"question": question})
    body = response.json()

    assert response.status_code == 200
    assert calls == [question], "服务层应收到原始问题"
    assert body["question"] == question
    assert body["answer"] == SNEAKY_ANSWER
    assert body["policy"]["passed"] is False
    assert body["policy"]["violations"]


@allure.feature("接口契约")
@allure.story("问题首尾空白会被去掉")
def test_question_is_stripped(client: TestClient, mock_ai_answer) -> None:
    calls = mock_ai_answer(answer=SAFE_REFUSAL)

    response = client.post("/chat", json={"question": "  生鲜能退吗？  "})

    assert response.status_code == 200
    assert calls == ["生鲜能退吗？"]
    assert response.json()["question"] == "生鲜能退吗？"


@allure.feature("接口契约")
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({}, id="missing_field"),
        pytest.param({"question": ""}, id="empty"),
        pytest.param({"question": "   "}, id="blank"),
        pytest.param({"question": "问" * (MAX_QUESTION_LENGTH + 1)}, id="too_long"),
        pytest.param({"question": 123}, id="wrong_type"),
    ],
)
def test_invalid_request_returns_422(client: TestClient, payload: dict) -> None:
    response = client.post("/chat", json=payload)

    assert response.status_code == 422


@allure.feature("接口契约")
@allure.story("上游失败必须显式报错")
def test_upstream_failure_returns_502(
    client: TestClient, mock_ai_answer
) -> None:
    mock_ai_answer(error=LLMServiceError("调用模型失败：connection reset"))

    response = client.post("/chat", json={"question": "生鲜能退吗？"})

    assert response.status_code == 502
    assert "调用模型失败" in response.json()["detail"]


@allure.feature("接口契约")
@allure.story("缺少 API Key 时返回 503 而不是 200")
def test_missing_api_key_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 置空而非删除：.env 会被 load_dotenv 重新填充，空字符串则不会
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    response = client.post("/chat", json={"question": "生鲜能退吗？"})

    assert response.status_code == 503
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]
