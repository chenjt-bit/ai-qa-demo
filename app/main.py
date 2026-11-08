"""FastAPI 入口层：只做参数校验、调用服务层、把结果和合规判定返回给调用方。"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.config import ConfigError
from app.llm_service import LLMServiceError, get_ai_answer
from app.policy import PolicyVerdict, check_answer

# 单条问题的长度上限：防止超长输入带来的成本与延迟风险
MAX_QUESTION_LENGTH = 2000

app = FastAPI(title="AI QA Demo")


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="用户问题，去空白后长度需在 1~2000 之间",
    )

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question 不能为空白")
        return stripped


class ChatResponse(BaseModel):
    question: str
    answer: str
    policy: PolicyVerdict = Field(description="回答的合规判定结果")


@app.get("/health")
def get_status() -> dict[str, str]:
    return {"status": "OK"}


@app.post("/chat", response_model=ChatResponse)
def post_chat(req: ChatRequest) -> ChatResponse:
    try:
        answer = get_ai_answer(req.question)
    except ConfigError as exc:
        # 配置缺失属于部署问题，不是客户端的错
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMServiceError as exc:
        # 上游模型不可用：明确失败，绝不返回 200 + 错误文案
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(
        question=req.question,
        answer=answer,
        policy=check_answer(answer),
    )
