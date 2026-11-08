"""Prompt 注入 / 越狱防护测试（Mock 层，秒级，进每次 CI）。

这里的 Mock 不是「伪造一个安全回答再断言它安全」，而是
**假设模型已经被攻破**，验证接口的合规闸门能不能拦住——
只有这样，快速用例才真的在测被测系统，而不是在测 mock。
"""

from __future__ import annotations

import allure
import pytest
from fastapi.testclient import TestClient

from tests.payloads import (
    ATTACK_PAYLOADS,
    JAILBROKEN_ANSWER,
    SAFE_REFUSAL,
    AttackPayload,
    payload_ids,
)

PAYLOADS = pytest.mark.parametrize("payload", ATTACK_PAYLOADS, ids=payload_ids())


@allure.feature("AI 安全测试")
@allure.story("Prompt 注入防护")
@PAYLOADS
def test_jailbroken_answer_is_blocked(
    client: TestClient, mock_ai_answer, payload: AttackPayload
) -> None:
    with allure.step(f"模拟被「{payload.tactic}」攻破后的模型回答"):
        calls = mock_ai_answer(answer=JAILBROKEN_ANSWER)

    with allure.step("发送攻击载荷"):
        response = client.post("/chat", json={"question": payload.question})
        body = response.json()

    with allure.step("校验合规闸门是否拦截"):
        assert response.status_code == 200, "模型被攻破不应导致接口 5xx"
        assert calls == [payload.question], "攻击载荷应原样透传到服务层"
        assert body["policy"]["passed"] is False, "被攻破的回答必须标记为不合规"
        assert body["policy"]["violations"], "违规时必须给出命中的规则"
        assert body["answer"] == JAILBROKEN_ANSWER, "接口应如实返回模型原文供排查"


@allure.feature("AI 安全测试")
@allure.story("Prompt 注入防护")
@PAYLOADS
def test_refusal_is_not_flagged(
    client: TestClient, mock_ai_answer, payload: AttackPayload
) -> None:
    with allure.step("模拟模型顶住攻击、给出合规拒绝"):
        mock_ai_answer(answer=SAFE_REFUSAL)

    with allure.step("发送同一个攻击载荷"):
        response = client.post("/chat", json={"question": payload.question})
        body = response.json()

    with allure.step("合规拒绝不应被误杀"):
        assert response.status_code == 200
        assert body["policy"]["passed"] is True, (
            f"合规拒绝被误判为违规：{body['policy']['reason']}"
        )
