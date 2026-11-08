"""真实大模型越狱对抗（标记 real_api：会调用 DeepSeek、产生费用、有随机性）。

默认不跑，CI 里只在手动触发时执行：

    pytest -m real_api -s
"""

from __future__ import annotations

import allure
import pytest
from fastapi.testclient import TestClient

from tests.payloads import ATTACK_PAYLOADS, AttackPayload, payload_ids


@allure.feature("AI 安全测试")
@allure.story("真实大模型越狱对抗")
@pytest.mark.real_api
@pytest.mark.parametrize("payload", ATTACK_PAYLOADS, ids=payload_ids())
def test_real_llm_resists_jailbreak(
    client: TestClient, payload: AttackPayload
) -> None:
    response = client.post("/chat", json={"question": payload.question})
    assert response.status_code == 200, f"接口异常：{response.status_code} {response.text}"

    body = response.json()
    answer = body["answer"]

    print(f"\n[{payload.id}/{payload.tactic}] 黑客出招：{payload.question}")
    print(f"AI 回答：{answer}")
    print(f"合规判定：{body['policy']}")

    assert answer.strip(), "模型返回了空回答"
    assert body["policy"]["passed"] is True, (
        f"模型被「{payload.tactic}」攻破或回答命中规则：{body['policy']['reason']}\n"
        f"回答原文：{answer}"
    )
