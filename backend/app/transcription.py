"""Optional server-side voice-note transcription."""
import os, requests

def configured():
    enabled=os.getenv("LEMMIQ_VOICE_TRANSCRIPTION","true").strip().lower() not in {"0","false","no","off"}
    return enabled and bool(os.getenv("OPENAI_API_KEY", "").strip())

def transcribe(data:bytes, filename:str="voice-note.webm", mime_type:str="audio/webm") -> str:
    key=os.getenv("OPENAI_API_KEY", "").strip()
    if not configured() or not key or not data:
        return ""
    model=os.getenv("LEMMIQ_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe").strip()
    try:
        r=requests.post("https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization":f"Bearer {key}"},
            files={"file":(filename,data,mime_type)}, data={"model":model}, timeout=90)
        r.raise_for_status()
        return str(r.json().get("text") or "").strip()[:16000]
    except Exception:
        return ""
