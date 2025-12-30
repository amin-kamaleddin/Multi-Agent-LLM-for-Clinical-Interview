from __future__ import annotations

import os
from typing import Iterator, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from elevenlabs.client import ElevenLabs


router = APIRouter()


def _client() -> ElevenLabs:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY not configured")
    return ElevenLabs(api_key=api_key)


def _default_voice_id() -> str:
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not voice_id:
        raise HTTPException(status_code=500, detail="ELEVENLABS_VOICE_ID not configured")
    return voice_id


@router.post("/voice/tts")
async def tts(body: dict) -> StreamingResponse:
    """Stream text-to-speech audio via ElevenLabs SDK as MPEG."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    voice_id = (body.get("voiceId") or _default_voice_id())

    client = _client()

    def gen() -> Iterator[bytes]:
        # Use ElevenLabs streaming API via SDK
        stream = client.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            model_id="eleven_flash_v2_5",
        )
        for chunk in stream:
            if isinstance(chunk, bytes):
                yield chunk

    return StreamingResponse(gen(), media_type="audio/mpeg")


@router.post("/voice/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    """Transcribe uploaded audio using ElevenLabs SDK STT.

    The client should POST audio (e.g., audio/webm or audio/mpeg).
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio")

    client = _client()
    try:
        # ElevenLabs SDK STT: requires file and model_id
        result = client.speech_to_text.convert(
            file=data,
            model_id="scribe_v1",
        )
        # Normalize to a simple shape (supports SDK model, dict, or str)
        text = None
        if hasattr(result, "text"):
            try:
                text = getattr(result, "text")
            except Exception:
                text = None
        if text is None and isinstance(result, dict):
            text = result.get("text")
        if text is None and isinstance(result, str):
            text = result
        return {"text": str(text or "")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"transcription failed: {e}")


@router.get("/voice/tts")
async def tts_get(text: str, voiceId: Optional[str] = None) -> StreamingResponse:
    """GET variant for streaming TTS so the client can set audio.src directly."""
    text = (text or "").strip()    
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    voice_id = (voiceId or _default_voice_id())

    client = _client()

    def gen() -> Iterator[bytes]:
        stream = client.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            model_id="eleven_flash_v2_5",
        )
        for chunk in stream:
            if isinstance(chunk, bytes):
                yield chunk

    return StreamingResponse(gen(), media_type="audio/mpeg")


