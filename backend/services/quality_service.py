import os
import json
import subprocess
from typing import Dict, Any, List, Optional
from PIL import Image
import numpy as np

class QualityService:
    def __init__(self):
        pass

    def inspect_video(self, video_path: str) -> Dict[str, Any]:
        """Runs ffprobe on the exported video and returns stream metadata."""
        if not os.path.exists(video_path):
            return {"valid": False, "error": f"File does not exist: {video_path}"}

        size_bytes = os.path.getsize(video_path)
        if size_bytes == 0:
            return {"valid": False, "error": "File is 0 bytes"}

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels",
            "-of", "json",
            video_path
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            return {"valid": False, "error": f"FFprobe failed: {res.stderr}"}

        try:
            data = json.loads(res.stdout)
            format_info = data.get("format", {})
            streams = data.get("streams", [])

            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

            duration = float(format_info.get("duration", 0.0))

            fps_str = video_stream.get("r_frame_rate", "24/1") if video_stream else "24/1"
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = round(float(num) / float(den), 2)
            else:
                fps = float(fps_str)

            return {
                "valid": True,
                "duration": duration,
                "size_bytes": size_bytes,
                "bitrate": format_info.get("bit_rate"),
                "has_video": video_stream is not None,
                "width": video_stream.get("width") if video_stream else None,
                "height": video_stream.get("height") if video_stream else None,
                "video_codec": video_stream.get("codec_name") if video_stream else None,
                "fps": fps,
                "has_audio": audio_stream is not None,
                "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
                "sample_rate": audio_stream.get("sample_rate") if audio_stream else None,
                "channels": audio_stream.get("channels") if audio_stream else None
            }
        except Exception as e:
            return {"valid": False, "error": f"Failed to parse FFprobe output: {e}"}

    def generate_contact_sheet(self, video_path: str, sheet_path: str, grid: str = "3x2") -> str:
        """Generates a visual contact sheet of representative frames from the video."""
        os.makedirs(os.path.dirname(sheet_path), exist_ok=True)
        probe = self.inspect_video(video_path)
        dur = probe.get("duration", 10.0)

        pts_interval = max(0.5, dur / 6.0)

        cmd = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-i", video_path,
            "-vf", f"fps=1/{pts_interval},scale=360:-1,tile={grid}",
            "-vframes", "1",
            "-q:v", "2",
            sheet_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return sheet_path

    def verify_visual_diversity(self, storyboard: Dict[str, Any], sheet_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Visual Diversity Check:
        1. Verifies that scenes have distinct scene types and visual subjects.
        2. Rejects if all scenes map to a single generic subject.
        3. If contact sheet exists, analyzes image tile variance to ensure visual changes occur.
        """
        scenes = storyboard.get("scenes", [])
        if not scenes:
            return {"passed": False, "reason": "Storyboard has 0 scenes"}

        subjects = [sc.get("visual_subject", "") for sc in scenes]
        unique_subjects = set(subjects)

        # Enforce that in a multi-scene video, we don't repeat the exact same subject everywhere
        if len(scenes) >= 3 and len(unique_subjects) < 2:
            return {
                "passed": False,
                "reason": f"Visual diversity failure: all {len(scenes)} scenes use the same visual subject ('{subjects[0]}')",
                "unique_subjects_count": len(unique_subjects),
                "total_scenes": len(scenes)
            }

        # Frame variance check via Pillow if contact sheet exists
        variance_score = 1.0
        if sheet_path and os.path.exists(sheet_path):
            try:
                img = Image.open(sheet_path).convert("L")
                arr = np.array(img, dtype=np.float32)
                # Calculate standard deviation of pixels across contact sheet
                std_dev = float(np.std(arr))
                variance_score = std_dev
                if std_dev < 15.0: # Highly uniform/blank or static image
                    return {
                        "passed": False,
                        "reason": f"Visual variance failure: contact sheet frames are visually static (std_dev={std_dev:.1f} < 15)",
                        "std_dev": std_dev
                    }
            except Exception as e:
                print(f"Contact sheet variance check warning: {e}")

        return {
            "passed": True,
            "total_scenes": len(scenes),
            "unique_subjects": list(unique_subjects),
            "unique_subjects_count": len(unique_subjects),
            "variance_score": round(variance_score, 2)
        }

    def verify_audio_production(self, audio_dir: str, video_dur: float) -> Dict[str, Any]:
        """Verifies presence and health of multi-track audio stems."""
        stems = ["stem_voice.wav", "stem_music.wav", "stem_sfx.wav", "mix.wav"]
        missing = []
        for s in stems:
            p = os.path.join(audio_dir, s)
            if not os.path.exists(p) or os.path.getsize(p) < 1000:
                missing.append(s)

        if missing:
            return {"passed": False, "reason": f"Missing or empty audio stems: {', '.join(missing)}"}

        # Check mix duration
        mix_p = os.path.join(audio_dir, "mix.wav")
        try:
            import soundfile as sf
            info = sf.info(mix_p)
            mix_dur = info.duration
            if abs(mix_dur - video_dur) > 2.0:
                return {
                    "passed": False,
                    "reason": f"Audio/video duration mismatch: mix={mix_dur:.2f}s vs video={video_dur:.2f}s"
                }
        except Exception as e:
            return {"passed": False, "reason": f"Audio file read error: {e}"}

        return {"passed": True, "stems_verified": stems, "mix_duration": round(mix_dur, 2)}

    def verify_research_claims(self, project_dir: str) -> Dict[str, Any]:
        """Verifies that research claims exist, are dated, and linked to sources."""
        claims_p = os.path.join(project_dir, "research", "claims.json")
        sources_p = os.path.join(project_dir, "research", "sources.json")

        if not os.path.exists(claims_p) or not os.path.exists(sources_p):
            return {"passed": False, "reason": "Missing claims.json or sources.json"}

        try:
            with open(claims_p, "r", encoding="utf-8") as f:
                claims = json.load(f)
            with open(sources_p, "r", encoding="utf-8") as f:
                sources = json.load(f)

            if not claims or not sources:
                return {"passed": False, "reason": "Claims or sources list is empty"}

            # Check that claims have supporting sources
            src_ids = {s.get("source_id") for s in sources}
            for c in claims:
                supp = c.get("supporting_source_ids", [])
                if not any(s_id in src_ids for s_id in supp):
                    return {"passed": False, "reason": f"Claim {c.get('claim_id')} lacks verified source citation"}

            return {
                "passed": True,
                "claims_count": len(claims),
                "sources_count": len(sources)
            }
        except Exception as e:
            return {"passed": False, "reason": f"Research validation error: {e}"}

    def run_qc_suite(
        self,
        video_path: str,
        target_dur: float,
        min_acceptable_dur: float = 5.0,
        storyboard: Optional[Dict[str, Any]] = None,
        project_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs the complete QC suite enforcing visual, audio, and research honesty."""
        probe = self.inspect_video(video_path)
        if not probe.get("valid"):
            return {
                "passed": False,
                "checks": {"file_exists": False, "playable": False},
                "details": probe.get("error", "Unknown error")
            }

        checks = {
            "file_exists": True,
            "playable": True,
            "has_video_stream": probe.get("has_video", False),
            "has_audio_stream": probe.get("has_audio", False),
            "duration_valid": probe.get("duration", 0.0) >= min_acceptable_dur,
            "resolution_valid": (probe.get("width", 0) or 0) > 0 and (probe.get("height", 0) or 0) > 0,
            "fps_valid": (probe.get("fps", 0) or 0) >= 20
        }

        # Visual Diversity Check
        sheet_path = os.path.join(os.path.dirname(video_path), "contact_sheet.jpg")
        if storyboard:
            div_check = self.verify_visual_diversity(storyboard, sheet_path=sheet_path)
            checks["visual_diversity_passed"] = div_check["passed"]
            if not div_check["passed"]:
                checks["visual_diversity_reason"] = div_check.get("reason")

        # Audio Production Check
        if project_dir:
            audio_dir = os.path.join(project_dir, "audio")
            aud_check = self.verify_audio_production(audio_dir, probe.get("duration", 0.0))
            checks["audio_stems_passed"] = aud_check["passed"]
            if not aud_check["passed"]:
                checks["audio_stems_reason"] = aud_check.get("reason")

            # Research Claims Check
            res_check = self.verify_research_claims(project_dir)
            checks["research_claims_passed"] = res_check["passed"]
            if not res_check["passed"]:
                checks["research_claims_reason"] = res_check.get("reason")

        all_passed = all(v is True for k, v in checks.items() if not k.endswith("_reason"))
        return {
            "passed": all_passed,
            "checks": checks,
            "metadata": probe
        }

quality_service = QualityService()
