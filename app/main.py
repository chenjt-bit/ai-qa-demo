from fastapi import FastAPI
from pydantic import BaseModel
from app.llm_service import get_ai_answer

# 实例化FastAPI类
app = FastAPI(title="AI QA Demo")

class ChatRequest(BaseModel):
    question:str

class ChatResponse(BaseModel):
    question:str
    answer:str

@app.get("/health")
def get_status():
    return {"status":"OK"}

@app.post("/chat",response_model=ChatResponse)
def post_chat(req:ChatRequest):
    real_answer = get_ai_answer(req.question)
    return ChatResponse(question=req.question, answer=real_answer)