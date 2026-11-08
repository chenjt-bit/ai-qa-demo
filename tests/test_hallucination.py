from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)


# 场景 1：AI 表现良好，没有幻觉
@patch("app.main.get_ai_answer")  # 拦截 app.main 里对 llm_service 的调用
def test_no_hallucination(mock_get_answer):
    # 我们强行让 AI 返回一个正确的回答（模拟理想情况）
    mock_get_answer.return_value = "您好，生鲜食品是不支持退货的哦。"

    response = client.post("/chat", json={"question": "生鲜能退吗？"})
    data = response.json()

    assert response.status_code == 200
    # 幻觉检测规则：回答中不能出现“可以退”、“支持退货”等违背规则的字眼
    assert "不支持" in data["answer"]
    assert "可以退" not in data["answer"]


# 场景 2：抓出 AI 的幻觉（强行让 AI 犯错，看测试能不能抓出来）
@patch("app.main.get_ai_answer")
def test_detect_hallucination(mock_get_answer):
    # 我们模拟 AI 发生了幻觉，给出了违背原则的回答
    mock_get_answer.return_value = "亲，生鲜只要没拆包装，是可以退的哦！"

    response = client.post("/chat", json={"question": "生鲜能退吗？"})
    data = response.json()

    # 测试期望：如果 AI 产生幻觉，我们的测试脚本必须能“拦截”它！
    # 注意：这里我们在验证“AI 说了错话”。所以断言里我们故意查它有没有胡说。
    has_hallucination = "可以退" in data["answer"]
    assert has_hallucination is True  # 证明我们成功模拟并捕捉到了幻觉