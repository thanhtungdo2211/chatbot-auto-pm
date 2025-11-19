# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from agent import Agent
from typing import Optional 
app = FastAPI(title="ChatBot API", description="Chatbot with Redis memory and LLM", version="1.0")

# Khởi tạo agent toàn cục (có thể dùng lại giữa các request)
agent = Agent()

# Định nghĩa input schema
class ChatRequest(BaseModel):
    user_id: int
    query: Optional[str] = None
    file_content: Optional[str] = None
    long_memory: Optional[str] = None  # True = session mode, False = non-session mode

# ✅ Endpoint chính
@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    response = agent.query(
        user_id=request.user_id,
        query=request.query,
        file_content=request.file_content,
        long_memory=request.long_memory
    )

    return {
        "user_id": request.user_id,
        "query": request.query,
        "response": response
    }

# ✅ Kiểm tra API hoạt động
@app.get("/")
def root():
    return {"message": "ChatBot API is running 🚀"}
