"""校验器自身的单元测试——这一层才是「测试有意义」的地基。

Mock 测试如果只断言「我伪造的回答里没有禁用词」，等于什么都没测；
真正该被单测的是 :func:`app.policy.check_answer` 的判定逻辑。
"""

from __future__ import annotations

import allure
import pytest

from app.policy import JUDGE_RULE, SYSTEM_PROMPT, check_answer, find_violations

SAFE_ANSWERS = [
    "对不起，根据平台规则，生鲜食品不支持退货。",
    "亲，生鲜食品是不可以退的哦。",  # 含「可以退」子串，但语义是否定（子串匹配会误杀）
    "亲，生鲜不能退，但服装支持7天无理由退货。",
    "生鲜食品不支持7天无理由退货。",
    "您好，生鲜类商品不支持退货，也无法承诺退款或补偿。",
    "服装支持7天无理由退货；生鲜食品绝对不允许退货。",
    "",
]

VIOLATING_ANSWERS = [
    "生鲜可以退货。",
    "生鲜随时可以退，您放心。",
    "亲，生鲜只要没拆包装，是可以退的哦！",
    "生鲜退货是没问题的。",
    "可以给您退一半的钱作为补偿。",
    "生鲜商品如遇质量问题可以退款。",
]


@allure.feature("合规校验器")
@allure.story("合规回答不应被误判")
@pytest.mark.parametrize("answer", SAFE_ANSWERS)
def test_safe_answer_passes(answer: str) -> None:
    with allure.step(f"校验回答：{answer!r}"):
        verdict = check_answer(answer)

    assert verdict.passed is True, f"被误判为违规：{verdict.reason}"
    assert verdict.violations == []


@allure.feature("合规校验器")
@allure.story("违规回答必须被拦截")
@pytest.mark.parametrize("answer", VIOLATING_ANSWERS)
def test_violating_answer_fails(answer: str) -> None:
    with allure.step(f"校验回答：{answer!r}"):
        verdict = check_answer(answer)

    assert verdict.passed is False, f"漏判：{answer!r}"
    assert verdict.violations, "违规时必须给出命中的规则"
    assert verdict.reason.startswith("疑似违规")


def test_violations_are_not_duplicated() -> None:
    """同一句话同时命中多条规则时，每条规则只出现一次。"""
    verdict = check_answer("生鲜随时可以退，生鲜可以退款。")

    assert verdict.passed is False
    assert len(verdict.violations) == len(set(verdict.violations))


def test_find_violations_returns_empty_for_blank_answer() -> None:
    """空回答交给异常路径处理，不应被当成违规。"""
    assert find_violations("   ") == []


def test_prompt_and_judge_rule_stay_in_sync() -> None:
    """系统提示词与裁判规则必须描述同一套业务约束，防止改一处漏一处。"""
    assert "生鲜" in SYSTEM_PROMPT
    assert "生鲜" in JUDGE_RULE
    assert "7天无理由" in SYSTEM_PROMPT
