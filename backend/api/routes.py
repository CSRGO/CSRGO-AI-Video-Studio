import os
import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from backend.services.ai_service import ai_service

from backend.services.ollama_service import ollama_service
from backend.services.ollama_manager import ollama_manager
from backend.services.health_service import check_ollama, check_ffmpeg, check_gpu
from backend.services.style_service import style_service
from backend.services.tts_service import tts_service
from backend.services.project_service import project_service, PROJECTS_DIR, OUTPUT_DIR
from backend.services.github_service import github_service
from backend.services.research_service import research_service

router = APIRouter()

# --- Request / Response Models ---
class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    model: str | None = None

class ProjectCreateRequest(BaseModel):
    name: Optional[str] = None
    topic: str = Field(min_length=1, max_length=2000)
    mode: str = "topic" # topic or github
    source_url: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list, max_length=6)
    expressive_voice: bool = True
    target_duration: int = Field(default=45, ge=10, le=120) # # 15, 30, 45, 60, 90, 120
    aspect_ratio: Literal["9:16", "16:9", "1:1", "4:5"] = "9:16" # 9:16, 16:9, 1:1, 4:5
    resolution: str = "1080x1920"
    fps: int = Field(default=24, ge=20, le=30)
    language: Literal["en", "en-us", "en-gb", "zh", "hi", "es", "fr", "it", "ja", "pt"] = "en"
    voice: str = "af_bella"
    speaking_speed: float = Field(default=1.0, ge=.85, le=1.2)
    style_slug: str = "swiss-motion"
    music_enabled: bool = True
    sfx_enabled: bool = True
    subtitles_enabled: bool = True
    draft_render: bool = False

    @field_validator("source_urls")
    @classmethod
    def validate_urls(cls, urls):
        from urllib.parse import urlsplit
        for url in urls:
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Sources must be HTTP(S) article URLs without credentials")
        return urls

class ResearchInputsRequest(BaseModel):
    source_urls: List[str] = Field(default_factory=list, max_length=6)

    @field_validator("source_urls")
    @classmethod
    def validate_urls(cls, urls):
        return ProjectCreateRequest.validate_urls(urls)

class GitHubAnalyzeRequest(BaseModel):
    url: str

class ResearchSearchRequest(BaseModel):
    query: str

class StoryboardUpdateRequest(BaseModel):
    storyboard: dict

# --- System & Diagnostics ---
@router.get("/health")
def health():
    cfg = ai_service.public_config()
    try:
        ai_service.check_ready()
        ai_status = {**cfg, "ready": True}
    except RuntimeError as exc:
        ai_status = {**cfg, "ready": False, "last_error": str(exc)}
    ollama_stat = {"status": "online" if cfg["provider"] == "ollama" and ai_status["ready"] else "offline"}
    ffmpeg_stat = check_ffmpeg()
    gpu_stat = check_gpu()
    voices = tts_service.get_voices()

    return {
        "status": "ok" if ai_status["ready"] else "degraded",
        "ai": ai_status,
        "ollama": ollama_stat,
        "ffmpeg": ffmpeg_stat,
        "gpu": gpu_stat,
        "tts": {
            "engine": "Kokoro ONNX (Offline)",
            "status": "available" if len(voices) > 0 else "error",
            "voices_count": len(voices)
        },
        "styles_count": len(style_service.list_styles())
    }

class AISettingsRequest(BaseModel):
    provider: Literal["ollama", "freellmapi"]
    endpoint: str = Field(max_length=500)
    planning_model: str = Field(min_length=1, max_length=200)
    coding_model: str = Field(min_length=1, max_length=200)
    api_key_env: str = Field(default="FREELLMAPI_API_KEY", max_length=100)
    timeout_seconds: int = Field(default=180, ge=30, le=600)

@router.get("/ai/settings")
def ai_settings():
    return ai_service.public_config()

@router.put("/ai/settings")
def update_ai_settings(request: AISettingsRequest):
    try:
        with project_service._lock:
            if any(j["status"] == "running" for j in project_service._active_jobs.values()):
                raise ValueError("Wait for active video production to finish before switching models.")
            return ai_service.update(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

class SessionCredential(BaseModel):
    api_key: str = Field(min_length=1, max_length=1000, repr=False)

@router.post("/ai/credential")
def set_session_credential(request: SessionCredential):
    with project_service._lock:
        if any(j["status"] == "running" for j in project_service._active_jobs.values()):
            raise HTTPException(status_code=409, detail="Wait for production to finish before changing credentials.")
        ai_service._session_key = request.api_key
    return {"configured": True, "storage": "backend process memory only"}

@router.get("/ai/status")
def ai_status():
    try:
        return {**ai_service.check_ready(), "ready": True}
    except RuntimeError as exc:
        return {**ai_service.public_config(), "ready": False, "last_error": str(exc)}

@router.post("/ai/initialize")
def ai_initialize():
    try:
        ai_service.check_ready()
        response = ai_service.generate("Reply with exactly READY.")
        return {"ready": bool(response.strip()), "engine": "Claude Code"}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@router.get("/models")
def models():
    try:
        return ollama_service.list_models()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@router.post("/generate")
def generate(request: GenerateRequest):
    try:
        return {"response": ollama_service.generate(request.prompt, request.model)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

# --- Research Search ---
@router.post("/research/search")
def test_search(req: ResearchSearchRequest):
    try:
        return research_service.search_web(req.query, max_results=5)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# --- Style Library ---
@router.get("/styles")
def list_styles(category: Optional[str] = None, search: Optional[str] = None):
    styles = style_service.list_styles(search=search, category=category)
    categories = style_service.get_categories()
    return {
        "count": len(styles),
        "categories": categories,
        "styles": styles
    }

@router.get("/styles/{slug}")
def get_style(slug: str):
    style = style_service.get_style(slug)
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")
    return style

@router.get("/styles/{slug}/poster")
def get_style_poster(slug: str):
    style = style_service.get_style(slug)
    if not style or not style.get("poster_path") or not os.path.exists(style["poster_path"]):
        raise HTTPException(status_code=404, detail="Poster image not found")
    return FileResponse(style["poster_path"], media_type="image/jpeg")

# --- Voice Library ---
@router.get("/voices")
def list_voices():
    return {
        "voices": tts_service.get_voices()
    }

# --- GitHub Analysis ---
@router.post("/analyze-github")
def analyze_github(request: GitHubAnalyzeRequest):
    temp_dir = os.path.join(PROJECTS_DIR, ".tmp_analysis")
    try:
        res = github_service.analyze_repository(request.url, temp_dir)
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# --- Project Management & Video Pipeline ---
@router.post("/projects")
def create_project(request: ProjectCreateRequest):
    try:
        proj = project_service.create_project(request.dict())
        return proj
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/projects")
def list_projects():
    return project_service.list_projects()

@router.get("/projects/{project_id}")
def get_project(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj

@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    try:
        success = project_service.delete_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except OSError:
        raise HTTPException(status_code=500, detail="Some files could not be removed. Close any video player using them, then retry deletion.")
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "message": "Video, exports, workspace, research, audio and render jobs deleted"}

@router.post("/projects/{project_id}/produce")
def produce_video(project_id: str):
    try:
        job = project_service.start_production(project_id)
        return {"status": "started", "job": job}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/projects/{project_id}/status")
def get_project_status(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    job = project_service.get_active_job(project_id)
    return {
        "id": proj["id"],
        "status": proj["status"],
        "stage": proj["stage"],
        "progress": proj["progress"],
        "error_message": proj["error_message"],
        "actual_duration": proj["actual_duration"],
        "output_video_path": proj["output_video_path"],
        "job": job
    }

@router.get("/projects/{project_id}/research-inputs")
def get_research_inputs(project_id: str):
    try:
        return project_service.research_inputs(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.put("/projects/{project_id}/research-inputs")
def update_research_inputs(project_id: str, request: ResearchInputsRequest):
    try:
        return project_service.research_inputs(project_id, request.source_urls)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.get("/projects/{project_id}/research")
def get_project_research(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    res_path = os.path.join(PROJECTS_DIR, proj["slug"], "research", "research.json")
    if not os.path.exists(res_path):
        raise HTTPException(status_code=404, detail="Research report not found")
    with open(res_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/projects/{project_id}/treatment")
def get_project_treatment(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    t_path = os.path.join(PROJECTS_DIR, proj["slug"], "script", "TREATMENT.md")
    shot_path = os.path.join(PROJECTS_DIR, proj["slug"], "script", "SHOT_LIST.json")

    treatment_text = open(t_path, "r", encoding="utf-8").read() if os.path.exists(t_path) else ""
    shot_list = json.load(open(shot_path, "r", encoding="utf-8")) if os.path.exists(shot_path) else []

    return {
        "treatment": treatment_text,
        "shot_list": shot_list
    }

@router.get("/projects/{project_id}/video")
def get_project_video(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj or not proj.get("output_video_path") or not os.path.exists(proj["output_video_path"]):
        raise HTTPException(status_code=404, detail="Video file not available")
    return FileResponse(proj["output_video_path"], media_type="video/mp4")

@router.get("/projects/{project_id}/preview")
def get_project_preview(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj or not proj.get("preview_video_path") or not os.path.exists(proj["preview_video_path"]):
        raise HTTPException(status_code=404, detail="Preview video not available")
    return FileResponse(proj["preview_video_path"], media_type="video/mp4")

@router.get("/projects/{project_id}/thumbnail")
def get_project_thumbnail(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj or not proj.get("thumbnail_path") or not os.path.exists(proj["thumbnail_path"]):
        raise HTTPException(status_code=404, detail="Thumbnail not available")
    return FileResponse(proj["thumbnail_path"], media_type="image/jpeg")

@router.get("/projects/{project_id}/contact-sheet")
def get_contact_sheet(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    sheet_path = os.path.join(PROJECTS_DIR, proj["slug"], "renders", "contact_sheet.jpg")
    if not os.path.exists(sheet_path):
        raise HTTPException(status_code=404, detail="Contact sheet not available")
    return FileResponse(sheet_path, media_type="image/jpeg")

@router.get("/projects/{project_id}/storyboard")
def get_storyboard(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    sb_path = os.path.join(PROJECTS_DIR, proj["slug"], "storyboard", "storyboard.json")
    if not os.path.exists(sb_path):
        raise HTTPException(status_code=404, detail="Storyboard not found")
    with open(sb_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.put("/projects/{project_id}/storyboard")
def update_storyboard(project_id: str, req: StoryboardUpdateRequest):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    sb_path = os.path.join(PROJECTS_DIR, proj["slug"], "storyboard", "storyboard.json")
    with open(sb_path, "w", encoding="utf-8") as f:
        json.dump(req.storyboard, f, indent=2)
    return {"success": True, "message": "Storyboard updated"}

@router.get("/projects/{project_id}/srt")
def get_srt(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    srt_path = os.path.join(PROJECTS_DIR, proj["slug"], "subtitles", f"{proj['slug']}.srt")
    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail="SRT file not found")
    return FileResponse(srt_path, media_type="text/plain", filename=f"{proj['slug']}.srt")

@router.get("/projects/{project_id}/sources")
def get_sources(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    p = os.path.join(PROJECTS_DIR, proj["slug"], "research", "sources.json")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Sources not found")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/projects/{project_id}/claims")
def get_claims(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    p = os.path.join(PROJECTS_DIR, proj["slug"], "research", "claims.json")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Claims not found")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/projects/{project_id}/research-report")
def get_research_report(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    p = os.path.join(PROJECTS_DIR, proj["slug"], "research", "research_report.md")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Research report not found")
    with open(p, "r", encoding="utf-8") as f:
        return {"report": f.read()}

@router.get("/projects/{project_id}/audio-cues")
def get_audio_cues(project_id: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    p = os.path.join(PROJECTS_DIR, proj["slug"], "audio", "audio_cues.json")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Audio cues not found")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/projects/{project_id}/audio/stem/{stem_name}")
def get_audio_stem(project_id: str, stem_name: str):
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    stem_file = f"{stem_name}.wav" if not stem_name.endswith(".wav") else stem_name
    p = os.path.join(PROJECTS_DIR, proj["slug"], "audio", stem_file)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail=f"Audio stem '{stem_name}' not found")
    return FileResponse(p, media_type="audio/wav", filename=stem_file)

