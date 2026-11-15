import os
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
        self._voices_cache = []

    def _get_engine(self):
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
                        name = v.capitalize()

                    categorized.append({
                        "id": v,
                        "name": f"{name} ({gender}, {accent})",
                        "gender": gender,
                        "accent": accent,
                        "tag": v
                    })
                self._voices_cache = categorized
            except Exception as e:
                # Fallback voice list if model not loaded yet
                self._voices_cache = [
                    {"id": "af_bella", "name": "Bella (Female, American)", "gender": "Female", "accent": "American", "tag": "af_bella"},
                    {"id": "af_sarah", "name": "Sarah (Female, American)", "gender": "Female", "accent": "American", "tag": "af_sarah"},
                    {"id": "am_michael", "name": "Michael (Male, American)", "gender": "Male", "accent": "American", "tag": "am_michael"},
                    {"id": "am_adam", "name": "Adam (Male, American)", "gender": "Male", "accent": "American", "tag": "am_adam"},
                    {"id": "bf_emma", "name": "Emma (Female, British)", "gender": "Female", "accent": "British", "tag": "bf_emma"},
                    {"id": "bm_george", "name": "George (Male, British)", "gender": "Male", "accent": "British", "tag": "bm_george"}
                ]
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

    def synthesize_scenes(self, scenes: List[Dict[str, Any]], out_dir: str, voice: str = "af_bella", speed: float = 1.0) -> List[Dict[str, Any]]:
        """
        Synthesize audio for each scene in the storyboard, save individual wav files,
        and generate a master combined narration track.
        """
        os.makedirs(out_dir, exist_ok=True)
        results = []
        all_samples = []
        sample_rate = 24000
        current_time = 0.0

        for i, scene in enumerate(scenes, 1):
            narration = scene.get("narration", "").strip()
            wav_filename = f"scene_{i:02d}.wav"
            wav_path = os.path.join(out_dir, wav_filename)

            if narration:
                samples, sr = self.synthesize_line(narration, voice=voice, speed=speed)
                sample_rate = sr
                sf.write(wav_path, samples, sr)
                dur = len(samples) / float(sr)
            else:
                dur = 2.0
                samples = np.zeros(int(dur * sample_rate), dtype=np.float32)
                sf.write(wav_path, samples, sample_rate)

            start_t = current_time
            end_t = start_t + dur
            current_time = end_t + 0.35  # Natural pause between scenes

            # Append to master with short pause
            pause_samples = np.zeros(int(0.35 * sample_rate), dtype=np.float32)
            all_samples.append(samples)
            all_samples.append(pause_samples)

            results.append({
                "scene_index": i,
                "narration": narration,
                "audio_file": wav_filename,
                "audio_path": wav_path,
                "start_time": round(start_t, 2),
                "end_time": round(end_t, 2),
                "duration": round(dur, 2)
            })

        # Save concatenated full narration track
        if all_samples:
            full_track = np.concatenate(all_samples)
            master_wav_path = os.path.join(out_dir, "narration_full.wav")
            sf.write(master_wav_path, full_track, sample_rate)

        return results

tts_service = TTSService()

if __name__ == "__main__":
    ensure_kokoro_models()

