import subprocess
import httpx
from backend.core.config import settings

async def check_ollama():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(settings.ollama_base_url + "/api/tags")
            response.raise_for_status()
            return {"status": "online", "models": [m["name"] for m in response.json().get("models", [])]}
    except Exception as exc:
        return {"status": "offline", "error": str(exc)}

def check_ffmpeg():
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        return {"status": "available" if result.returncode == 0 else "error", "version": result.stdout.splitlines()[0] if result.stdout else "Unknown"}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}

def check_gpu():
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"], capture_output=True, text=True, timeout=5)
        return {"status": "available", "details": result.stdout.strip()} if result.returncode == 0 else {"status": "unavailable"}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}
