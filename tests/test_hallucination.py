"""幻觉检测（Mock 层，秒级）。

三个方向一起覆盖，缺一不可：
1. 合规回答 → 放行；
2. 含「可以退」子串的合规否定句 → 放行（防子串误杀）；
3. 真正的幻觉回答 → 拦截。
"""

from __future__ import annotations

import allure
from fastapi.testclient import TestClient

from tests.payloads import HALLUCINATED_ANSWER, NEGATED_REFUSAL, SAFE_REFUSAL


@allure.feature("AI 幻觉检测")
@allure.story("合规回答放行")
def test_safe_answer_is_not_flagged(
    client: TestClient, mock_ai_answer
) -> None:
    mock_ai_answer(answer=SAFE_REFUSAL)

    response = client.post("/chat", json={"question": "生鲜能退吗？"})
    body = response.json()

    assert response.status_code == 200
    assert body["policy"]["passed"] is True
    assert body["policy"]["violations"] == []


@allure.feature("AI 幻觉检测")
@allure.story("否定句不应被子串匹配误杀")
def test_negated_refusal_is_not_flagged(
    client: TestClient, mock_ai_answer
) -> None:
    """「生鲜食品是不可以退的」包含「可以退」，旧版断言会在这里误报。"""
    mock_ai_answer(answer=NEGATED_REFUSAL)

    response = client.post("/chat", json={"question": "生鲜能退吗？"})
    body = response.json()

    assert response.status_code == 200
    assert body["policy"]["passed"] is True, body["policy"]["reason"]


@allure.feature("AI 幻觉检测")
@allure.story("幻觉回答必须被拦截")
def test_hallucination_is_caught(
    client: TestClient, mock_ai_answer
) -> None:
    mock_ai_answer(answer=HALLUCINATED_ANSWER)

    response = client.post("/chat", json={"question": "生鲜能退吗？"})
    body = response.json()

    assert response.status_code == 200
    assert body["policy"]["passed"] is False
    assert body["policy"]["violations"], "必须说明命中了哪条规则"
