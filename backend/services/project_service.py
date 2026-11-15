import os
import json
import time
import uuid
import shutil
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.database.db import get_connection
from backend.services.ai_service import ai_service
from backend.services.lemo_loader import lemo_loader
from pathlib import Path
from backend.services.claude_animation_worker import claude_animation_worker
from backend.services.research_service import research_service
from backend.services.script_service import script_service
from backend.services.github_service import github_service
from backend.services.tts_service import tts_service
from backend.services.audio_service import audio_service
from backend.services.visual_service import visual_service
from backend.services.render_service import render_service
from backend.services.subtitle_service import subtitle_service
from backend.services.quality_service import quality_service

PROJECTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "projects"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "output"))

class ProjectService:
    def __init__(self):
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _slugify(self, text: str) -> str:
        clean = "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower()).strip("-")
        return clean[:40] or "video-project"

    def _row_to_dict(self, row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        d = dict(row)
        d["music_enabled"] = bool(d.get("music_enabled", 1))
        d["sfx_enabled"] = bool(d.get("sfx_enabled", 1))
        d["subtitles_enabled"] = bool(d.get("subtitles_enabled", 1))
        d["draft_render"] = bool(d.get("draft_render", 0))
        return d

    def create_project(self, data: Dict[str, Any]) -> Dict[str, Any]:
        lemo_loader.load_style_rule(data.get("style_slug", "swiss-motion"))
        if not 10 <= int(data.get("target_duration", 30)) <= 120:
            raise ValueError("Video duration must be between 10 and 120 seconds")
        proj_id = str(uuid.uuid4())
        name = data.get("name") or data.get("topic", "Untitled")[:40]
        base_slug = self._slugify(name)
        slug = f"{base_slug}-{proj_id[:6]}"
        now = datetime.now(timezone.utc).isoformat()

        project_dir = os.path.join(PROJECTS_DIR, slug)
        for sub in ("research", "script", "storyboard", "visuals", "audio", "subtitles", "renders", "final"):
            os.makedirs(os.path.join(project_dir, sub), exist_ok=True)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO projects (
            id, name, slug, topic, mode, source_url, target_duration,
            aspect_ratio, resolution, fps, language, voice, speaking_speed,
            style_slug, music_enabled, sfx_enabled, subtitles_enabled, draft_render,
            status, stage, progress, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            proj_id, name, slug, data.get("topic", ""), data.get("mode", "topic"),
            data.get("source_url"), int(data.get("target_duration", 45)),
            data.get("aspect_ratio", "9:16"), data.get("resolution", "1080x1920"),
            int(data.get("fps", 24)), data.get("language", "en"),
            data.get("voice", "af_bella"), float(data.get("speaking_speed", 1.0)),
            data.get("style_slug", "swiss-motion"),
            1 if data.get("music_enabled", True) else 0,
            1 if data.get("sfx_enabled", True) else 0,
            1 if data.get("subtitles_enabled", True) else 0,
            1 if data.get("draft_render", False) else 0,
            "draft", "created", 0, now, now
        ))
        conn.commit()

        cursor.execute("SELECT * FROM projects WHERE id = ?", (proj_id,))
        row = cursor.fetchone()
        proj_dict = self._row_to_dict(row)
        conn.close()

        with open(os.path.join(project_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump(proj_dict, f, indent=2)

        # Non-secret project-specific preferences live beside the project assets.
        with open(os.path.join(project_dir, "preferences.json"), "w", encoding="utf-8") as f:
            json.dump({"source_urls": data.get("source_urls", []), "expressive_voice": data.get("expressive_voice", True)}, f)
        return proj_dict

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ? OR slug = ?", (project_id, project_id))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_dict(row)

    def list_projects(self) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(r) for r in rows]

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            proj = self.get_project(project_id)
            if not proj:
                return False
            if self._active_jobs.get(proj["id"], {}).get("status") == "running":
                raise ValueError("This video is being produced. Wait until production finishes before deleting it.")
            slug = proj["slug"]
            if slug != os.path.basename(slug) or slug in (".", ".."):
                raise ValueError("Invalid project path")
            project_dir = Path(PROJECTS_DIR) / slug
            if project_dir.is_symlink() or project_dir.resolve().parent != Path(PROJECTS_DIR).resolve():
                raise ValueError("Unsafe project path")
            # Delete assets first. An I/O failure retains the DB record so cleanup can be retried.
            if project_dir.exists():
                shutil.rmtree(project_dir)
            for asset in Path(OUTPUT_DIR).glob(slug + ".*"):
                if asset.is_file() or asset.is_symlink():
                    asset.unlink()
            conn = get_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM render_jobs WHERE project_id = ?", (proj["id"],))
                    conn.execute("DELETE FROM projects WHERE id = ?", (proj["id"],))
            finally:
                conn.close()
            self._active_jobs.pop(proj["id"], None)
            return True

    def update_project_status(self, project_id: str, stage: str, progress: int, status: str = "processing", error: str = None):
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE projects
        SET stage = ?, progress = ?, status = ?, error_message = ?, updated_at = ?
        WHERE id = ? OR slug = ?
        """, (stage, progress, status, error, now, project_id, project_id))
        conn.commit()
        conn.close()

    def get_active_job(self, project_id: str) -> Optional[Dict[str, Any]]:
        project = self.get_project(project_id)
        return self._active_jobs.get(project["id"]) if project else None

    def start_production(self, project_id: str) -> Dict[str, Any]:
        with self._lock:
            proj = self.get_project(project_id)
            if not proj:
                raise ValueError(f"Project not found: {project_id}")
            if any(job["status"] == "running" for job in self._active_jobs.values()):
                raise ValueError("A production is already running. Finish it before starting another video.")
            ai_service.check_ready()
            rule = lemo_loader.load_style_rule(proj["style_slug"])
            if "image-generation" in rule["metadata"].get("needs", []):
                raise ValueError("This style needs generated image assets. Choose a code-rendered style.")
            project_id = proj["id"]
            job_id = str(uuid.uuid4())
            self._active_jobs[project_id] = {
                "job_id": job_id, "project_id": project_id, "status": "running", "stage": "starting",
                "progress": 0, "message": "Checking production prerequisites…",
                "started_at": datetime.now(timezone.utc).isoformat()}
            self.update_project_status(project_id, "starting", 0)
            cfg = ai_service.config()
            threading.Thread(target=self._production_context, args=(project_id, job_id, cfg), daemon=True).start()
            return dict(self._active_jobs[project_id])

    def _production_context(self, project_id, job_id, cfg):
        with ai_service.production():
            from backend.services.ai_service import _snapshot
            token = _snapshot.set(cfg)
            try:
                self._run_pipeline(project_id, job_id)
            finally:
                _snapshot.reset(token)

    def _run_pipeline(self, project_id: str, job_id: str):
        proj = self.get_project(project_id)
        slug = proj["slug"]
        project_dir = os.path.join(PROJECTS_DIR, slug)

        def update_job(stage: str, progress: int, msg: str):
            if project_id in self._active_jobs:
                self._active_jobs[project_id].update({
                    "stage": stage,
                    "progress": progress,
                    "message": msg
                })
            self.update_project_status(project_id, stage, progress, status="processing")

        try:
            # -------------------------------------------------------------
            # Stage 0: Local AI Engine & Claude Code Readiness Check
            # -------------------------------------------------------------
            update_job("init_ai", 3, "Checking Claude Code, model provider and rendering tools…")
            ai_service.check_ready()
            preferences_path = os.path.join(project_dir, "preferences.json")
            preferences = {}
            if os.path.exists(preferences_path):
                with open(preferences_path, encoding="utf-8") as f:
                    preferences = json.load(f)
            with open(os.path.join(project_dir, "generation.json"), "w", encoding="utf-8") as f:
                json.dump(ai_service.public_config(), f, indent=2)

            # -------------------------------------------------------------
            # Stage 1: Internet Research Engine & Fact Gathering
            # -------------------------------------------------------------
            update_job("research", 8, f"Executing web research for '{proj['topic']}'...")
            research_dir = os.path.join(project_dir, "research")

            def research_prog(sub_st, pct, msg):
                update_job("research", int(5 + pct * .15), msg)
            sources = preferences.get("source_urls", [])
            if proj.get("mode") == "github" and proj.get("source_url"):
                sources = [proj["source_url"]] + sources
            research_brief = research_service.research_topic(
                topic=proj["topic"], out_dir=research_dir, progress_cb=research_prog, source_urls=sources)

            # -------------------------------------------------------------
            # Stage 2: Story Treatment (DIRECTOR.md principles & 3s Hook)
            # -------------------------------------------------------------
            update_job("treatment", 22, "Directing story treatment and 3-second visual hook...")
            treatment_md = script_service.generate_treatment(
                topic=proj["topic"],
                research_brief=research_brief,
                target_duration=proj["target_duration"],
                style_slug=proj["style_slug"]
            )
            with open(os.path.join(project_dir, "script", "TREATMENT.md"), "w", encoding="utf-8") as f:
                f.write(treatment_md)

            # -------------------------------------------------------------
            # Stage 3: Visual Storyboard & Shot List Planning
            # -------------------------------------------------------------
            update_job("script", 30, f"Creating visual storyboard & shot list ({proj['target_duration']}s)...")
            storyboard = script_service.generate_storyboard(
                topic=proj["topic"],
                research_brief=research_brief,
                treatment_md=treatment_md,
                target_duration=proj["target_duration"],
                style_slug=proj["style_slug"],
                aspect_ratio=proj["aspect_ratio"],
                language=proj["language"]
            )
            with open(os.path.join(project_dir, "storyboard", "storyboard.json"), "w", encoding="utf-8") as f:
                json.dump(storyboard, f, indent=2)

            shot_list = script_service.generate_shot_list(storyboard)
            with open(os.path.join(project_dir, "script", "SHOT_LIST.json"), "w", encoding="utf-8") as f:
                json.dump(shot_list, f, indent=2)

            # -------------------------------------------------------------
            # Stage 4: Offline Voice Synthesis (Kokoro ONNX)
            # -------------------------------------------------------------
            update_job("voice", 42, f"Synthesizing offline speech ({proj['voice']})...")
            scenes = storyboard.get("scenes", [])
            audio_dir = os.path.join(project_dir, "audio")
            narration_timing = tts_service.synthesize_scenes(
                scenes=scenes,
                out_dir=audio_dir,
                voice=proj["voice"],
                speed=proj["speaking_speed"], language=proj["language"],
                target_duration=proj["target_duration"], expressive=preferences.get("expressive_voice", True)
            )
            with open(os.path.join(project_dir, "audio", "timing.json"), "w", encoding="utf-8") as f:
                json.dump(narration_timing, f, indent=2)

            # -------------------------------------------------------------
            # Stage 5: Subtitles (.srt)
            # -------------------------------------------------------------
            update_job("subtitles", 50, "Generating synchronized subtitles...")
            srt_path = os.path.join(project_dir, "subtitles", f"{slug}.srt")
            subtitle_service.generate_srt(narration_timing, srt_path)

            # -------------------------------------------------------------
            # Stage 6: Claude Code Dynamic Animation Component Generation
            # -------------------------------------------------------------
            update_job("claude_code", 52, f"Invoking Claude Code for {proj['style_slug']} animation components...")
            def comp_prog(pct, msg):
                update_job("claude_code", pct, msg)
            claude_animation_worker.generate_all_components(
                storyboard=storyboard,
                style_slug=proj["style_slug"],
                project_dir=project_dir,
                progress_cb=comp_prog
            )

            # -------------------------------------------------------------
            # Stage 7: Visual Simulation Engine (Interactive Workbench / DAG)
            # -------------------------------------------------------------
            update_job("visuals", 62, f"Generating visual simulation world ({storyboard.get('visual_archetype')})...")
            html_scene_path = os.path.join(project_dir, "visuals", "index.html")
            visual_service.generate_html_scene(
                storyboard=storyboard,
                narration_timing=narration_timing,
                style_slug=proj["style_slug"],
                aspect_ratio=proj["aspect_ratio"],
                output_html_path=html_scene_path,
                subtitles_enabled=proj["subtitles_enabled"]
            )

            visual_check = render_service.inspect_scenes(html_scene_path, os.path.join(project_dir, "renders", "style_frames"))
            with open(os.path.join(project_dir, "renders", "visual_check.json"), "w", encoding="utf-8") as f:
                json.dump(visual_check, f, indent=2)

            # -------------------------------------------------------------
            # Stage 7: Multi-Stem Procedural Audio Production
            # -------------------------------------------------------------
            update_job("audio_mix", 62, "Composing original score, multi-track stems, and event-based SFX...")
            actual_dur = float(proj["target_duration"])
            audio_prod = audio_service.build_multi_stem_production(
                duration_sec=actual_dur,
                project_dir=project_dir,
                project_slug=slug,
                narration_scenes=narration_timing,
                scenes_meta=[{**sc, "start": narration_timing[i]["start_time"],
                    "end": narration_timing[i+1]["start_time"] if i+1 < len(narration_timing) else actual_dur}
                    for i, sc in enumerate(storyboard["scenes"])],
                music_enabled=proj["music_enabled"],
                sfx_enabled=proj["sfx_enabled"],
                topic=proj.get("topic", ""), music_direction=storyboard.get("music_direction", {})
            )
            mix_wav_path = audio_prod["mix_path"]

            # -------------------------------------------------------------
            # Stage 8: Deterministic Video Frame Rendering (Playwright)
            # -------------------------------------------------------------
            update_job("rendering", 70, "Rendering visual simulation frames via Playwright Chromium...")
            w, h = visual_service.get_dimensions(proj["aspect_ratio"], draft=proj["draft_render"])
            fps = proj["fps"]
            raw_video_path = os.path.join(project_dir, "renders", "raw_video.mp4")

            def render_progress(pct, msg):
                update_job("rendering", pct, msg)

            render_service.render_video_frames(
                html_path=html_scene_path,
                output_video_path=raw_video_path,
                width=w,
                height=h,
                fps=fps,
                progress_cb=render_progress
            )

            # -------------------------------------------------------------
            # Stage 9: Mastering & Audio Muxing (-14 LUFS)
            # -------------------------------------------------------------
            update_job("muxing", 88, "Mastering audio to -14 LUFS and muxing final MP4...")
            final_mp4_path = os.path.join(project_dir, "final", f"{slug}.mp4")
            render_service.mux_video_audio(
                video_path=raw_video_path,
                audio_path=mix_wav_path,
                output_path=final_mp4_path,
                fps=fps
            )

            # -------------------------------------------------------------
            # Stage 10: Thumbnail, Preview & Quality Control Suite
            # -------------------------------------------------------------
            update_job("qc", 95, "Running automated QC suite & visual diversity check...")
            thumb_path = os.path.join(project_dir, "renders", "thumbnail.jpg")
            render_service.generate_thumbnail(final_mp4_path, thumb_path, at_second=min(2.0, actual_dur * 0.3))

            preview_path = os.path.join(project_dir, "renders", "preview.mp4")
            render_service.generate_preview(final_mp4_path, preview_path, max_height=640)

            contact_sheet_path = os.path.join(project_dir, "renders", "contact_sheet.jpg")
            quality_service.generate_contact_sheet(final_mp4_path, contact_sheet_path)

            qc_results = quality_service.run_qc_suite(
                final_mp4_path,
                target_dur=proj["target_duration"],
                storyboard=storyboard,
                project_dir=project_dir, expected_dimensions=(w, h), expected_fps=fps
            )
            with open(os.path.join(project_dir, "renders", "qc.json"), "w", encoding="utf-8") as f:
                json.dump(qc_results, f, indent=2)

            if not qc_results.get("passed"):
                failed = [name for name, value in qc_results.get("checks", {}).items() if value is False]
                raise RuntimeError("Quality checks failed: " + ", ".join(failed) + ". Inspect qc.json; video was not published.")

            # Export to global output folder
            global_output_mp4 = os.path.join(OUTPUT_DIR, f"{slug}.mp4")
            shutil.copyfile(final_mp4_path, global_output_mp4)

            # Update DB with final completion
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE projects
            SET status = 'completed', stage = 'completed', progress = 100,
                actual_duration = ?, output_video_path = ?, preview_video_path = ?, thumbnail_path = ?
            WHERE id = ?
            """, (round(actual_dur, 2), final_mp4_path, preview_path, thumb_path, project_id))
            conn.commit()
            conn.close()

            if project_id in self._active_jobs:
                self._active_jobs[project_id].update({
                    "status": "completed",
                    "stage": "completed",
                    "progress": 100,
                    "message": "Cinematic visual video produced successfully!",
                    "output_path": final_mp4_path,
                    "qc": qc_results
                })

        except Exception as exc:
            import traceback
            err_details = traceback.format_exc()
            print(f"Error producing video for project {project_id}: {err_details}")
            self.update_project_status(project_id, "failed", 0, status="failed", error=str(exc))
            if project_id in self._active_jobs:
                self._active_jobs[project_id].update({
                    "status": "failed",
                    "stage": "failed",
                    "error": str(exc),
                    "message": f"Production failed: {str(exc)}"
                })

project_service = ProjectService()
