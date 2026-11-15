import os
import threading
import re
import urllib.request
import numpy as np
import soundfile as sf
from typing import List, Dict, Any, Tuple, Optional

TTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "lemo-opuscar", "core", "tts"))
MODEL_PATH = os.path.join(TTS_DIR, "kokoro-v1.0.onnx")
VOICES_PATH = os.path.join(TTS_DIR, "voices-v1.0.bin")

KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_BIN_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

def _download_with_progress(url: str, dest_path: str, label: str):
    """Download a file over HTTP with progress reporting."""
    print(f"[Kokoro TTS] Downloading {label} from {url}...")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp_path = dest_path + ".tmp"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=180) as resp, open(tmp_path, "wb") as f:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB chunks
            last_percent = -1
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = int((downloaded / total_size) * 100)
                    if percent != last_percent and percent % 10 == 0:
                        print(f"   Downloading {label}: {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                        last_percent = percent
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(tmp_path, dest_path)
        print(f"[Kokoro TTS] Successfully installed {label} -> {dest_path}")
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise RuntimeError(f"Failed to download {label} from {url}: {e}")

def ensure_kokoro_models(force: bool = False):
    """Ensure Kokoro ONNX model and voices binary are downloaded and present."""
    os.makedirs(TTS_DIR, exist_ok=True)
    if force or not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) < 1000000:
        _download_with_progress(KOKORO_MODEL_URL, MODEL_PATH, "kokoro-v1.0.onnx")
    if force or not os.path.exists(VOICES_PATH) or os.path.getsize(VOICES_PATH) < 1000000:
        _download_with_progress(VOICES_BIN_URL, VOICES_PATH, "voices-v1.0.bin")

class TTSService:
    def __init__(self):
        self._kokoro = None
        self._engine_lock = threading.RLock()
        self._voices_cache = []

    def _get_engine(self):
        with self._engine_lock:
            if self._kokoro is None:
                if not os.path.exists(MODEL_PATH) or not os.path.exists(VOICES_PATH):
                    print(f"[Kokoro TTS] Model files not found. Auto-downloading...")
                    ensure_kokoro_models()
                from kokoro_onnx import Kokoro
                self._kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
            return self._kokoro

    def get_voices(self) -> List[Dict[str, str]]:
        if not self._voices_cache:
            try:
                engine = self._get_engine()
                raw_voices = engine.get_voices()
                categorized = []
                for v in sorted(raw_voices):
                    desc = v
                    gender = "Neutral"
                    accent = "US"
                    if v.startswith("af_"):
                        gender = "Female"
                        accent = "American"
                        name = v[3:].capitalize()
                    elif v.startswith("am_"):
                        gender = "Male"
                        accent = "American"
                        name = v[3:].capitalize()
                    elif v.startswith("bf_"):
                        gender = "Female"
                        accent = "British"
                        name = v[3:].capitalize()
                    elif v.startswith("bm_"):
                        gender = "Male"
                        accent = "British"
                        name = v[3:].capitalize()
                    elif v.startswith("zf_"):
                        gender = "Female"
                        accent = "Chinese"
                        name = v[3:].capitalize()
                    elif v.startswith("zm_"):
                        gender = "Male"
                        accent = "Chinese"
                        name = v[3:].capitalize()
                    else:
                        accents = {"h": "Hindi", "j": "Japanese", "f": "French", "e": "Spanish", "i": "Italian", "p": "Portuguese"}
                        accent = accents.get(v[:1], "Other")
                        gender = "Female" if v[1:2] == "f" else "Male" if v[1:2] == "m" else "Neutral"
                        name = v[3:].capitalize()

                    categorized.append({
                        "id": v,
                        "name": f"{name} ({gender}, {accent})",
                        "gender": gender,
                        "accent": accent,
                        "tag": v
                    })
                self._voices_cache = categorized
            except Exception as e:
                self.last_error = f"Kokoro model loading failed: {type(e).__name__}"
                return []
        return self._voices_cache

    def estimate_duration_seconds(self, text: str, speed: float = 1.0) -> float:
        """Estimate speech duration from text length (words/chars)."""
        words = len(text.strip().split())
        # Average English speech rate is ~140 words per minute -> 2.33 words/sec
        base_dur = max(1.2, (words / 2.33) / max(0.5, speed))
        return round(base_dur, 2)

    def trim_silence(self, samples: np.ndarray, sr: int, threshold: float = 0.01) -> np.ndarray:
        """Trim leading and trailing silence from audio samples."""
        if len(samples) == 0:
            return samples
        abs_samples = np.abs(samples)
        non_silent = np.where(abs_samples > threshold)[0]
        if len(non_silent) == 0:
            return samples
        start = max(0, non_silent[0] - int(0.05 * sr))
        end = min(len(samples), non_silent[-1] + int(0.08 * sr))
        return samples[start:end]

    def synthesize_line(self, text: str, voice: str = "af_bella", speed: float = 1.0, lang: str = "en-us") -> Tuple[np.ndarray, int]:
        """Synthesize a single text line into audio samples at sample rate."""
        engine = self._get_engine()
        # Clean text
        clean = re.sub(r'[\*\#\_\[\]]', '', text).strip()
        if not clean:
            # Return 0.5s silence
            return np.zeros(12000, dtype=np.float32), 24000

        samples, sr = engine.create(clean, voice=voice, speed=speed, lang=lang)
        trimmed = self.trim_silence(samples, sr)
        return trimmed, sr

    def _process_voice(self, samples, sr, pitch=1.0, tempo=1.0):
        """Small, formant-preserving pitch/rate changes using FFmpeg rubberband."""
        import subprocess
        result = subprocess.run([
            "ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
            "-af", f"rubberband=tempo={tempo:.5f}:pitch={pitch:.5f}:formant=preserved",
            "-f", "f32le", "pipe:1"], input=np.asarray(samples, dtype=np.float32).tobytes(),
            capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError("Expressive voice processing requires FFmpeg with the rubberband filter.")
        return np.frombuffer(result.stdout, dtype=np.float32).copy()

    def synthesize_scenes(self, scenes, out_dir, voice="af_bella", speed=1.0,
                          language="en", target_duration=None, expressive=True):
        os.makedirs(out_dir, exist_ok=True)
        langs = {"en": "en-us", "en-us": "en-us", "en-gb": "en-gb", "zh": "cmn", "hi": "hi",
                 "es": "es", "fr": "fr-fr", "it": "it", "ja": "ja", "pt": "pt-br"}
        if language not in langs:
            raise ValueError("Unsupported narration language")
        # Restrained delivery presets, not a claim of actor-level emotional synthesis.
        presets = {"neutral": (1., 1.), "curious": (1.025, .98), "warm": (.99, .96),
                   "excited": (1.045, 1.06), "serious": (.975, .95),
                   "concerned": (.98, .97), "reassuring": (.99, .96)}
        clips, sample_rate = [], 24000
        for scene in scenes:
            narration = scene.get("narration", "").strip()
            if not narration:
                raise RuntimeError("A scene is missing spoken narration.")
            pitch, rate = presets.get(scene.get("emotion", "neutral"), (1., 1.)) if expressive else (1., 1.)
            samples, sr = self.synthesize_line(narration, voice=voice, speed=speed * rate, lang=langs[language])
            if len(samples) < sr * .2 or float(np.max(np.abs(samples))) < .001:
                raise RuntimeError("Voice synthesis returned empty or silent speech.")
            if sr != sample_rate:
                import soxr
                samples = soxr.resample(samples, sr, sample_rate)
            if pitch != 1.:
                samples = self._process_voice(samples, sample_rate, pitch=pitch)
            clips.append(samples)
        pauses = [max(.08, min(.6, float(s.get("pause_after", .25)))) for s in scenes]
        natural_seconds = sum(len(c) / sample_rate for c in clips)
        if target_duration:
            available = target_duration - sum(pauses[:-1]) - .8
            tempo = natural_seconds / available
            if not .72 <= tempo <= 1.35:
                raise RuntimeError(f"Narration is {natural_seconds:.1f}s for a {target_duration}s video. Rewrite the script; speech will not be clipped or sped up excessively.")
            clips = [self._process_voice(c, sample_rate, tempo=tempo) for c in clips]
        results, full, current = [], [], 0.
        for i, (scene, samples, pause) in enumerate(zip(scenes, clips, pauses), 1):
            path = os.path.abspath(os.path.join(out_dir, f"scene_{i:02d}.wav"))
            sf.write(path, samples, sample_rate)
            duration = len(samples) / sample_rate
            results.append({"scene_index": i, "narration": scene["narration"],
                "audio_file": os.path.basename(path), "audio_path": path,
                "start_time": current, "end_time": current + duration, "duration": duration,
                "emotion": scene.get("emotion", "neutral"), "pause_after": pause})
            full.append(samples)
            current += duration
            if i < len(scenes):
                silence = np.zeros(round(pause * sample_rate), dtype=np.float32)
                full.append(silence)
                current += len(silence) / sample_rate
        sf.write(os.path.join(out_dir, "narration_full.wav"), np.concatenate(full), sample_rate)
        return results


tts_service = TTSService()

if __name__ == "__main__":
    ensure_kokoro_models()

