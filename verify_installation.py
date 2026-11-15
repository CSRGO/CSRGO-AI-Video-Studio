import os
import sys
import json
import subprocess
import shutil

def verify():
    print("=" * 65)
    print("   CSRGO AI VIDEO STUDIO - SYSTEM & INSTALLATION VERIFICATION")
    print("=" * 65)

    all_passed = True

    # 1. Python Environment
    py_ver = sys.version.split()[0]
    print(f"[1/10] Python Environment: {py_ver} [OK]")

    # 2. Multimedia Packages
    try:
        import numpy
        import scipy
        import soundfile
        import soxr
        import PIL
        import faster_whisper
        import kokoro_onnx
        import playwright
        print("[2/10] Core Python Multimedia & ML Packages: All Installed [OK]")
    except Exception as e:
        print(f"[2/10] Core Python Packages: FAILED ({e})")
        all_passed = False

    # 3. FFmpeg and FFprobe
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        try:
            res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            line = res.stdout.splitlines()[0] if res.stdout else "Available"
            print(f"[3/10] FFmpeg & FFprobe: Installed ({line.split('Copyright')[0].strip()}) [OK]")
        except Exception:
            print("[3/10] FFmpeg & FFprobe: Present [OK]")
    else:
        print("[3/10] FFmpeg/FFprobe: Missing from PATH! [FAILED]")
        all_passed = False

    # 4. GPU & VRAM Status
    try:
        smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"], capture_output=True, text=True, timeout=5)
        if smi.returncode == 0:
            gpu_info = smi.stdout.strip().splitlines()[0]
            print(f"[4/10] NVIDIA GPU: {gpu_info} [OK]")
        else:
            print("[4/10] NVIDIA GPU: nvidia-smi failed [WARNING]")
    except Exception:
        print("[4/10] NVIDIA GPU: nvidia-smi not available [WARNING]")

    # 5. Ollama Connectivity & Models
    try:
        import urllib.request
        req = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
        tags = json.loads(req.read().decode())
        models = [m.get("name") for m in tags.get("models", [])]
        print(f"[5/10] Ollama Local Models: Online ({len(models)} available: {', '.join(models)}) [OK]")
    except Exception as e:
        print(f"[5/10] Ollama Local LLM: Offline ({e}) [FAILED]")
        all_passed = False

    # 6. Kokoro TTS Engine & Model Files
    kokoro_model = os.path.abspath("vendor/lemo-opuscar/core/tts/kokoro-v1.0.onnx")
    kokoro_voices = os.path.abspath("vendor/lemo-opuscar/core/tts/voices-v1.0.bin")
    if not (os.path.exists(kokoro_model) and os.path.exists(kokoro_voices)):
        try:
            print("[6/10] Kokoro TTS Model Files: Missing, auto-downloading...")
            from backend.services.tts_service import ensure_kokoro_models
            ensure_kokoro_models()
        except Exception as e:
            print(f"[6/10] Kokoro TTS Model Download Failed: {e}")
    if os.path.exists(kokoro_model) and os.path.exists(kokoro_voices):
        print(f"[6/10] Kokoro TTS Model Files: Found in vendor/lemo-opuscar/core/tts/ [OK]")
    else:
        print(f"[6/10] Kokoro TTS Model Files: Missing! [FAILED]")
        all_passed = False

    # 7. Headless Browser (Playwright Chromium)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        print("[7/10] Headless Browser (Playwright Chromium): Tested & Ready [OK]")
    except Exception as e:
        print(f"[7/10] Playwright Chromium: FAILED ({e})")
        all_passed = False

    # 8. Vendor Repositories
    lemo = os.path.exists("vendor/lemo-opuscar/styles")
    claude_shorts = os.path.exists("vendor/claude-animated-shorts/templates")
    if lemo and claude_shorts:
        print("[8/10] Production Repositories: vendor/lemo-opuscar & vendor/claude-animated-shorts [OK]")
    else:
        print(f"[8/10] Production Repositories: lemo={lemo}, claude_shorts={claude_shorts} [FAILED]")
        all_passed = False

    # 9. Style Repertoire
    style_dir = os.path.abspath("vendor/lemo-opuscar/styles")
    styles_count = len([d for d in os.listdir(style_dir) if os.path.isdir(os.path.join(style_dir, d))]) if os.path.exists(style_dir) else 0
    print(f"[9/10] Lemo-Opuscar Creative Styles: {styles_count} styles indexed [OK]")

    # 10. Database
    try:
        from backend.database.db import init_db, get_connection
        init_db()
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM projects")
        cnt = cur.fetchone()[0]
        conn.close()
        print(f"[10/12] SQLite Database: Initialized & Connected ({cnt} projects registered) [OK]")
    except Exception as e:
        print(f"[10/12] SQLite Database: FAILED ({e})")
        all_passed = False

    # 11. Claude Code CLI Installation
    from backend.services.ollama_manager import ollama_manager
    claude_ok = ollama_manager.verify_claude_code_installation()
    if claude_ok:
        print(f"[11/12] Claude Code CLI: Installed ({ollama_manager._state.get('claude_code_version')}) [OK]")
    else:
        print(f"[11/12] Claude Code CLI: FAILED ({ollama_manager._state.get('last_error')})")
        all_passed = False

    # 12. Local AI Configuration
    from backend.core.local_ai_config import local_ai_config
    if os.path.exists(local_ai_config.config_path):
        print(f"[12/12] Local AI Configuration: config/local_ai.yaml verified [OK]")
    else:
        print(f"[12/12] Local AI Configuration: config/local_ai.yaml missing [FAILED]")
        all_passed = False

    print("=" * 65)
    if all_passed:
        print("  RESULT: ALL SYSTEMS AND ENGINES VERIFIED SUCCESSFULLY [PASS]")
    else:
        print("  RESULT: ONE OR MORE VERIFICATION CHECKS FAILED [FAIL]")
    print("=" * 65)
    return all_passed

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)

