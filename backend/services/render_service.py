import io
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright


class RenderService:
    def _launch(self, playwright):
        executable = os.environ.get('CHROMIUM_EXECUTABLE')
        if not executable and not Path(playwright.chromium.executable_path).exists():
            executable = shutil.which('chromium') or shutil.which('google-chrome')
        return playwright.chromium.launch(headless=True, executable_path=executable,
            args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'])

    def _page(self, browser, html_path, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        # Generated animations have no need for external access.
        page.route('http://**/*', lambda route: route.abort())
        page.route('https://**/*', lambda route: route.abort())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_content(Path(html_path).read_text(encoding='utf-8'), wait_until='load')
        page.wait_for_function('window.READY === true', timeout=15000)
        page._studio_cdp = page.context.new_cdp_session(page)
        if errors:
            raise RuntimeError('Scene JavaScript failed: ' + '; '.join(errors))
        return page, errors

    def _render(self, page, timestamp):
        import json
        result = page._studio_cdp.send('Runtime.evaluate', {
            'expression': 'window.render(' + json.dumps(timestamp) + ')',
            'timeout': 5000, 'returnByValue': True})
        if result.get('exceptionDetails'):
            raise RuntimeError('Generated scene execution failed: ' + result['exceptionDetails'].get('text', 'runtime error'))

    def inspect_scenes(self, html_path, output_dir, width=540, height=960):
        """Exercise each generated function at three times; reject blank/static shots."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        report = []
        middle_frames = []
        with sync_playwright() as p:
            browser = self._launch(p)
            try:
                page, errors = self._page(browser, html_path, width, height)
                for scene in page.evaluate('window.SCENES'):
                    frames = []
                    for j, progress in enumerate((.1, .5, .9)):
                        at = scene['start'] + progress * (scene['end'] - scene['start'])
                        self._render(page, at)
                        # Inspect the canvas alone so captions cannot fake visual motion.
                        data = page.locator('canvas').screenshot(type='png')
                        Path(output_dir, f"scene_{scene['index']:02d}_{j}.png").write_bytes(data)
                        arr = np.asarray(Image.open(io.BytesIO(data)).convert('RGB').resize((160, 160)), dtype=float)
                        if arr.std() < 5:
                            raise RuntimeError(f"Scene {scene['index']} is visually blank.")
                        frames.append(arr)
                    differences = [float(np.mean(np.abs(a - b))) for a, b in zip(frames, frames[1:])]
                    if max(differences) < .5:
                        raise RuntimeError(f"Scene {scene['index']} has no measurable animation.")
                    middle_frames.append(frames[1])
                    report.append({'scene': scene['index'], 'frame_differences': differences})
                if len(middle_frames) > 1 and all(float(np.mean(np.abs(middle_frames[0] - f))) < .5 for f in middle_frames[1:]):
                    raise RuntimeError('All generated scenes look identical.')
                if errors:
                    raise RuntimeError('Scene runtime errors: ' + '; '.join(errors))
            finally:
                browser.close()
        return {'passed': True, 'scenes': report}

    def render_video_frames(self, html_path, output_video_path, width=1080, height=1920, fps=24, progress_cb=None):
        Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = self._launch(p)
            proc = None
            try:
                page, errors = self._page(browser, html_path, width, height)
                duration = page.evaluate('window.DUR')
                if not duration or duration <= 0:
                    raise RuntimeError('Animation has no valid duration.')
                total = math.ceil(duration * fps)
                with tempfile.TemporaryFile() as stderr:
                    proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe',
                        '-framerate', str(fps), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264',
                        '-threads', '2', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', output_video_path], stdin=subprocess.PIPE, stderr=stderr)
                    for frame in range(total):
                        self._render(page, frame / fps)
                        if errors:
                            raise RuntimeError('Scene runtime error: ' + '; '.join(errors))
                        proc.stdin.write(page.screenshot(type='jpeg', quality=92))
                        if progress_cb and frame % max(1, fps // 2) == 0:
                            progress_cb(70 + int(frame / total * 16), f'Rendering frame {frame+1}/{total}')
                    proc.stdin.close()
                    proc.wait(timeout=120)
                    if proc.returncode:
                        stderr.seek(0)
                        raise RuntimeError('FFmpeg encoding failed: ' + stderr.read().decode()[-2000:])
            finally:
                if proc and proc.poll() is None:
                    proc.kill()
                    proc.wait()
                browser.close()
        return float(duration)

    def render_single_frame(self, html_path, output_image_path, width=1080, height=1920, at_second=0.):
        Path(output_image_path).parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = self._launch(p)
            try:
                page, errors = self._page(browser, html_path, width, height)
                self._render(page, at_second)
                if errors:
                    raise RuntimeError('; '.join(errors))
                page.screenshot(path=output_image_path)
            finally:
                browser.close()

    def _ffmpeg(self, args, timeout=120):
        result = subprocess.run(['ffmpeg', '-y', '-v', 'error'] + args, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError('FFmpeg failed: ' + result.stderr.decode(errors='replace')[-2000:])

    def mux_video_audio(self, video_path, audio_path, output_path, fps=24, progress_cb=None):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._ffmpeg(['-i', video_path, '-i', audio_path, '-filter_complex',
            '[1:a]loudnorm=I=-14:TP=-1.2:LRA=11[a]', '-map', '0:v:0', '-map', '[a]',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
            '-shortest', '-movflags', '+faststart', output_path])
        return output_path

    def generate_thumbnail(self, video_path, thumbnail_path, at_second=2.):
        self._ffmpeg(['-ss', str(at_second), '-i', video_path, '-frames:v', '1', '-q:v', '2', thumbnail_path])
        return thumbnail_path

    def generate_preview(self, video_path, preview_path, max_height=640):
        self._ffmpeg(['-i', video_path, '-vf', f'scale=-2:{max_height}', '-c:v', 'libx264',
                      '-threads', '2', '-preset', 'veryfast', '-crf', '24', '-c:a', 'aac', preview_path])
        return preview_path

render_service = RenderService()
