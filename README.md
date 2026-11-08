# AI QA Demo · 电商客服大模型的质量与安全测试样例

一个回答「**AI 应用该怎么测**」的最小可运行工程：被测对象是基于 DeepSeek 的电商客服 HTTP 接口，测试侧用 **pytest + Mock + 规则校验 + LLM-as-Judge + Allure + GitHub Actions** 演示分层测试与 Prompt 注入对抗。

业务规则只有两条，故意做得极简，把注意力留给测试方法：

1. 服装支持 7 天无理由退货；
2. 生鲜食品**绝对**不允许退货，也不能承诺任何形式的退款或补偿。

> 设计上的一条硬约束：**「模型挂了」和「模型说错话」必须是两件不同的事**。
> 上游失败会显式返回 5xx，绝不会被包装成一条 200 的正常回答——否则测试拿不到违规词，就会假绿。

---

## 目录结构

```
ai-qa-demo/
├─ app/
│  ├─ main.py            # FastAPI 入口：参数校验 → 调服务 → 附加合规判定
│  ├─ config.py          # 配置集中读取与校验（.env + 环境变量）
│  ├─ policy.py          # 业务规则 + 合规校验（否定感知），系统提示词也在此
│  ├─ llm_service.py     # 服务层：调用 DeepSeek，异常统一翻译成 LLMServiceError
│  └─ llm_judge.py       # LLM-as-Judge：语义级质检，附 JSON 解析与注入隔离
├─ tests/
│  ├─ conftest.py          # 假配置夹具、client 夹具、服务层 mock 夹具
│  ├─ payloads.py          # 共享攻击载荷与样本回答
│  ├─ test_policy.py       # 校验器单测：真阳性 / 真阴性
│  ├─ test_llm_service.py  # 服务层单测：请求构造、响应解析、异常翻译
│  ├─ test_api.py          # 接口契约：入参校验、502/503 错误路径
│  ├─ test_security.py     # 越狱防护：被攻破时必须拦截，合规拒绝不能误杀
│  ├─ test_hallucination.py# 幻觉检测：合规放行 / 否定句不误杀 / 幻觉拦截
│  ├─ test_real_attack.py  # 真实模型越狱对抗（real_api）
│  └─ test_llm_judge.py    # 裁判解析单测 + 真实裁判用例（real_api）
├─ scripts/
│  └─ check_llm.py       # 冒烟脚本：验证 .env、网络、Key、模型名，失败返回 1
├─ .github/workflows/
│  └─ ai-tests.yml       # lint → 快速测试 → 手动触发的真实测试
├─ requirements.txt
├─ pytest.ini
└─ .env.example
```

---

## 快速开始

> 环境要求：Python 3.10+（CI 使用 3.12），可访问 `api.deepseek.com`。
> 本地查看 Allure 报告还需要 [Allure CLI](https://allurereport.org/docs/install/) 与 Java。

```powershell
# 1. 虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS / Linux: source .venv/bin/activate

# 2. 依赖
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. 配置（复制后填入自己的 Key）
Copy-Item .env.example .env
```

```dotenv
DEEPSEEK_API_KEY=sk-你的真实Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
# DEEPSEEK_TIMEOUT=30
```

> `.env` 已被 `.gitignore` 忽略，**不要提交**；Key 只放本地 `.env` 与 GitHub Secrets。

### 先跑冒烟，再跑测试

```powershell
python scripts/check_llm.py     # 打印配置 + 一次真实问答；失败退出码 1
uvicorn app.main:app --reload --port 8000
```

---

## 接口契约

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查，`{"status": "OK"}` |
| `POST` | `/chat` | 客服问答，返回回答 + 合规判定 |

```powershell
curl.exe -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"question":"生鲜可以退吗？"}'
```

```json
{
  "question": "生鲜可以退吗？",
  "answer": "对不起，生鲜食品不支持退货。",
  "policy": {
    "passed": true,
    "reason": "未发现违背业务规则的表述",
    "violations": []
  }
}
```

`policy.passed` 是接口对本次回答的自检结论：`false` 时 `violations` 会列出命中的规则说明。调用方可以据此决定是否转人工、是否重试。

| 状态码 | 含义 |
| --- | --- |
| `200` | 模型正常返回（回答是否合规看 `policy.passed`） |
| `422` | 入参非法：缺失、空白、超 2000 字、类型错误 |
| `502` | 上游模型失败：网络、非 200、响应结构异常、空回答 |
| `503` | 服务端配置缺失（如 `DEEPSEEK_API_KEY` 未配置） |

---

## 测试设计

### 分层

```
┌──────────────────────────────────────────────┐
│ 真实大模型测试            real_api / 手动触发  │  慢、花钱、有随机性
│ test_real_attack.py · test_llm_judge.py       │
├──────────────────────────────────────────────┤
│ 接口与安全闸门             Mock / 每次 push    │  秒级、免费、确定性
│ test_api.py · test_security.py · test_hallucination.py │
├──────────────────────────────────────────────┤
│ 纯逻辑单测                 无 IO               │
│ test_policy.py · test_llm_service.py          │
└──────────────────────────────────────────────┘
```

关键原则：**Mock 层假设「模型已经被攻破」**，再验证接口的合规闸门能否拦住。如果只是伪造一个安全回答、再断言这个回答里没有违规词，那测的是 mock，不是被测系统。

### 用例矩阵

| 文件 | 用例数 | 标记 | 真调 API | 断言对象 |
| --- | --- | --- | --- | --- |
| `tests/test_policy.py` | 16 | — | 否 | 校验器：合规样本不误判、违规样本不漏判、空回答不误判 |
| `tests/test_llm_service.py` | 6 | — | 否 | 请求体（含 `temperature=0`）、响应解析、超时/非 200/坏 JSON/空回答/缺 Key |
| `tests/test_api.py` | 11 | — | 否 | 接口契约：字段透传、入参 422、上游 502、缺配置 503 |
| `tests/test_security.py` | 8 | — | 否 | 4 种越狱话术 ×（攻破后拦截 / 拒绝时不误杀） |
| `tests/test_hallucination.py` | 3 | — | 否 | 合规放行、否定句不误杀、幻觉拦截 |
| `tests/test_llm_judge.py` | 8 | — | 否 | 裁判 JSON 解析、异常输入、prompt 注入隔离 |
| `tests/test_llm_judge.py` | 2 | `real_api` | 是 | 裁判能抓「退一半钱」式变相承诺，且不把合规拒绝判错 |
| `tests/test_real_attack.py` | 4 | `real_api` | 是 | 真实模型面对 4 种越狱话术时的实际表现 |

合计 **52 个快速用例 + 6 个真实用例**。

### 运行

```powershell
pytest -v -m "not real_api"     # 快速层（CI 默认）
pytest -v -m real_api -s        # 真实层（产生费用，约 9 秒）
pytest -v                       # 全部
```

本地查看 Allure：

```powershell
pytest -m "not real_api" --alluredir=./allure-results
allure serve ./allure-results
```

---

## 合规校验是怎么做的

`app/policy.py` 把「什么算违规」固化成可单测的函数，而不是散落在测试里的 `assert "可以退" not in answer`：

1. **5 条正则规则**：承诺生鲜可退、以生鲜为对象的退货承诺、声称生鲜退货没问题、无条件退货、退款/补偿承诺；
2. **否定感知**：命中片段回到原文、按小句回溯，若主张词（`可以/能/支持/退款/补偿`…）前出现否定词（`不/没/无/无法/禁止`…）则视为合规。
   所以「生鲜**不**可以退」不会因为包含「可以退」被子串匹配误杀；
3. **judge 兜底**：字面规则覆盖不了「退一半的钱作为补偿」这种变相承诺，`app/llm_judge.py` 用裁判模型做语义判定。裁判的回答被 `<<<ANSWER ... ANSWER>>>` 包住并声明「只当数据」，防止被测回答反向注入裁判。

规则表是有意写得直白、可读、可扩展的——它是**启发式断言**，不是语义理解，边界见下方「已知限制」。

---

## CI 流水线

| Job | 触发条件 | 内容 |
| --- | --- | --- |
| `lint` | push / PR | `ruff check .` |
| `fast-tests` | push / PR（依赖 lint） | 装依赖 → `pytest -m "not real_api"` → 生成 Allure 报告 → 上传制品（保留 7 天） |
| `real-api-tests` | 仅 `workflow_dispatch` | 注入 `secrets.DEEPSEEK_API_KEY` → `pytest -m real_api -s` → 上传结果 |

- 依赖用 `setup-python` 的 pip 缓存；同一分支重复触发会取消旧运行（`concurrency`）。
- Allure 报告只在 **push 到 main** 时生成并发布到 `gh-pages`，PR 阶段不尝试推送，避免 fork PR 因权限失败。
- 启用真实测试前，需在 **Settings → Secrets and variables → Actions** 添加 `DEEPSEEK_API_KEY`。

---

## 配置项

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | ✅ | 无 | 缺失或仍为占位符时，`/chat` 返回 503 |
| `DEEPSEEK_BASE_URL` | ❌ | `https://api.deepseek.com` | 兼容 OpenAI 协议的其他网关 |
| `DEEPSEEK_MODEL` | ❌ | `deepseek-chat` | 被测与裁判共用的模型 |
| `DEEPSEEK_TIMEOUT` | ❌ | `30` | 单次请求超时（秒），必须是正数 |

---

## 已知限制

| 限制 | 影响 |
| --- | --- |
| 规则校验是正则 + 否定词启发式 | 双重否定、跨句承诺、换行绕过、同义改写仍可能漏判；也可能误判「质量问题可退款」这类边界表述 |
| 真实用例依赖外部模型 | 即使 `temperature=0` 也不是严格确定，偶发波动；一次运行 6 次调用，有额度成本 |
| 无重试与限流 | 上游抖动直接表现为 502，真实用例随之失败 |
| 无鉴权、无请求级日志与指标 | 仅适合本地演示与流水线验证，不可直接上生产 |
| 关键词与裁判都不理解业务上下文 | 规则外的合理例外（如质量问题）一律按违规处理，需按真实业务再细化 |

---

## Roadmap

- [ ] 规则改为「业务策略表 + 语义判定」两层，支持按品类配置例外
- [ ] 引入 `pytest-rerunfailures` 与失败样本归档，量化真实用例的稳定性
- [ ] 为 `/chat` 增加超时重试、请求 ID 与结构化日志
- [ ] 用 OpenAPI schema 做契约测试（响应结构变更即失败）
- [ ] 覆盖率门槛（`pytest-cov`）+ CI 缓存与并行
- [ ] 提供 Dockerfile 与一键启动脚本

---

## 说明

本项目为学习/演示用途，规则与 Prompt 均为示例。API Key 请自行保管，一旦泄露立即轮换。
