from fastapi import FastAPI
from pydantic import BaseModel

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
    answer = f"这是假回答，你的问题是：{req.question}"
    return ChatResponse(question=req.question, answer=answer)