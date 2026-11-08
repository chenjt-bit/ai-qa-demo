"""冒烟脚本：确认 .env、网络、Key、模型名是否都正常。

用法：
    python scripts/check_llm.py

成功时打印模型回答并以 0 退出；任何失败都打印原因并以 1 退出，
方便在 CI 或本地排错时直接看退出码。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许直接以脚本方式运行（python scripts/check_llm.py）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    # 延迟导入：先把项目根目录放进 sys.path，再导入 app 包
    from app.config import ConfigError, get_settings
    from app.llm_service import LLMServiceError, get_ai_answer

    try:
        settings = get_settings()
    except ConfigError as exc:
        print(f"[配置错误] {exc}")
        return 1

    print("Key 是否读到：", bool(settings.api_key))
    print("Base URL：", settings.base_url)
    print("Model：", settings.model)
    print("Timeout：", settings.timeout)

    try:
        answer = get_ai_answer("用一句话介绍你自己")
    except LLMServiceError as exc:
        print(f"[调用失败] {exc}")
        return 1

    print("模型回答：", answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
