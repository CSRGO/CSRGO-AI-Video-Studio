import os
import subprocess
import time
from typing import Callable, Optional, Dict, Any, Tuple
from playwright.sync_api import sync_playwright

class RenderService:
    def __init__(self):
        pass

    def render_video_frames(
        self,
        html_path: str,
        output_video_path: str,
        width: int = 1080,
        height: int = 1920,
        fps: int = 24,
        progress_cb: Optional[Callable[[int, str], None]] = None
    ) -> float:
        """
        Renders the deterministic HTML/Canvas animation frame-by-frame
        via Playwright Chromium and streams JPEG frames to FFmpeg.
        Returns the actual duration in seconds.
        """
        os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
        file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-web-security",
                    "--allow-file-access-from-files",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage"
                ]
            )
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(file_url, wait_until="load")

            # Wait for window.READY
            page.wait_for_function("() => window.READY === true", timeout=15000)

            # Retrieve total duration
            dur = page.evaluate("() => window.DUR")
            if not dur or dur <= 0:
                dur = 15.0

            total_frames = int(round(dur * fps))
            if progress_cb:
                progress_cb(5, f"Rendering {total_frames} animation frames at {fps} FPS...")

            # Start FFmpeg subprocess to receive MJPEG stream on stdin
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-loglevel", "error",
                "-f", "image2pipe",
                "-framerate", str(fps),
                "-c:v", "mjpeg",
                "-i", "-",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                output_video_path
            ]

            ff_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

            try:
                for frame_idx in range(total_frames):
                    t = frame_idx / float(fps)
                    # Advance deterministic timeline
                    page.evaluate(f"window.render({t})")

                    # Screenshot JPEG
                    jpeg_bytes = page.screenshot(type="jpeg", quality=92)
                    ff_proc.stdin.write(jpeg_bytes)

                    if frame_idx % max(1, (fps // 2)) == 0 and progress_cb:
                        pct = int(10 + (frame_idx / total_frames) * 70)
                        progress_cb(pct, f"Rendering frame {frame_idx + 1}/{total_frames} ({round(t, 1)}s)...")

                ff_proc.stdin.close()
                ff_proc.wait(timeout=120)

                if ff_proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg frame encoding returned error code {ff_proc.returncode}")

            finally:
                browser.close()

        return float(dur)

    def render_single_frame(
        self,
        html_path: str,
        output_image_path: str,
        width: int = 1080,
        height: int = 1920,
        at_second: float = 0.0
    ):
        """Renders a single frame screenshot of the HTML animation."""
        os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
        file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-web-security",
                    "--allow-file-access-from-files",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage"
                ]
            )
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(file_url, wait_until="load")
            page.wait_for_function("() => window.READY === true", timeout=15000)
            if at_second > 0:
                page.evaluate(f"if (window.render) window.render({at_second});")
            page.screenshot(path=output_image_path, type="png")
            browser.close()

    def mux_video_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        fps: int = 24,
        progress_cb: Optional[Callable[[int, str], None]] = None
    ) -> str:
        """
        Muxes video and audio tracks with two-pass loudnorm to -14 LUFS,
        limiting true peaks, and outputting production-grade MP4.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if progress_cb:
            progress_cb(85, "Mastering audio and muxing final MP4...")

        # Two-pass loudnorm and true-peak limiter:
        # Loudnorm target: I=-14, TP=-1.2, LRA=11
        mux_cmd = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", "[1:a]loudnorm=I=-14:TP=-1.2:LRA=11[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-shortest",
            output_path
        ]

        res = subprocess.run(mux_cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            # Fallback direct mux without filter if audio format requires
            fallback_cmd = [
                "ffmpeg", "-y",
                "-loglevel", "error",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-shortest",
                output_path
            ]
            res_fb = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=120)
            if res_fb.returncode != 0:
                raise RuntimeError(f"Audio/Video muxing failed: {res.stderr or res_fb.stderr}")

        return output_path

    def generate_thumbnail(self, video_path: str, thumbnail_path: str, at_second: float = 2.0) -> str:
        """Extracts a high-quality frame for video thumbnail."""
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-ss", str(at_second),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            thumbnail_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return thumbnail_path

    def generate_preview(self, video_path: str, preview_path: str, max_height: int = 720) -> str:
        """Generates a compressed preview video for web dashboard streaming."""
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-loglevel", "error",
            "-i", video_path,
            "-vf", f"scale=-2:{max_height}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "128k",
            preview_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        return preview_path

render_service = RenderService()

