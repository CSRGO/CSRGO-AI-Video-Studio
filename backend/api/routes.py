import os
import json
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

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
    target_duration: int = 45 # 15, 30, 45, 60, 90, 120
    aspect_ratio: str = "9:16" # 9:16, 16:9, 1:1, 4:5
    resolution: str = "1080x1920"
    fps: int = 24
    language: str = "en"
    voice: str = "af_bella"
    speaking_speed: float = 1.0
    style_slug: str = "swiss-motion"
    music_enabled: bool = True
    sfx_enabled: bool = True
    subtitles_enabled: bool = True
    draft_render: bool = False

class GitHubAnalyzeRequest(BaseModel):
    url: str

class ResearchSearchRequest(BaseModel):
    query: str

class StoryboardUpdateRequest(BaseModel):
    storyboard: dict

# --- System & Diagnostics ---
@router.get("/health")
async def health():
    ollama_stat = await check_ollama()
    ffmpeg_stat = check_ffmpeg()
    gpu_stat = check_gpu()
    voices = tts_service.get_voices()

    return {
        "status": "ok",
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

@router.get("/ai/status")
def ai_status():
    return ollama_manager.get_status()

@router.post("/ai/initialize")
def ai_initialize():
    return ollama_manager.verify_and_initialize()

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
    success = project_service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "message": "Project deleted"}

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

