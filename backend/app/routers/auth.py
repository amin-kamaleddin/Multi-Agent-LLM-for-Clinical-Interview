import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(req: LoginRequest):
    expected = os.getenv("APP_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=500, detail="APP_PASSWORD not configured")
    if req.password != expected:
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"ok": True}



