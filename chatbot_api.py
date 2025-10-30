from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import ai_backends

app = FastAPI(title="Local Chatbot API")


class ChatRequest(BaseModel):
    model: Optional[str] = None
    query: str
    context: Optional[Dict] = {}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        resp = ai_backends.get_response(req.model, req.query, req.context or {})
        return {"response": resp}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
