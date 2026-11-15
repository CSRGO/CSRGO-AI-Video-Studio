#!/usr/bin/env python3
"""
CSRGO AI Video Studio — Comprehensive Diagnostics Script
Verifies all local hardware, runtime dependencies, offline models, and video engines.
"""
import sys
import os
import subprocess
import json

def check_mark(ok):
    return "[OK]" if ok else "[FAIL]"

def run():
    print("=" * 60)
    print("   CSRGO AI VIDEO STUDIO - SYSTEM & HARDWARE DIAGNOSTICS")
    print("=" * 60)
    print()

    all_passed = True

    # 1. Python Environment
    py_ver = sys.version.split()[0]
    is_311 = sys.version_info.major == 3 and sys.version_info.minor == 11
    print(f"1. Python Runtime: {py_ver} {check_mark(is_311)}")
    if not is_311:
        print("   Notice: Python 3.11 is recommended.")

    # 2. FFmpeg & FFprobe
    ffmpeg_ok = False
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            first_line = r.stdout.splitlines()[0]
            print(f"2. FFmpeg Encoder: {first_line} {check_mark(True)}")
            ffmpeg_ok = True
    except Exception as e:
        print(f"2. FFmpeg Encoder: Not found ({e}) {check_mark(False)}")
        all_passed = False

    # 3. GPU Detection
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            print(f"3. NVIDIA GPU: {r.stdout.strip()} {check_mark(True)}")
        else:
            print(f"3. NVIDIA GPU: Non-zero exit {check_mark(False)}")
    except Exception as e:
        print(f"3. NVIDIA GPU: nvidia-smi failed ({e}) [INFO: CPU Fallback Active]")

    # 4. Ollama Service & Models
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name") for m in data.get("models", [])]
            has_qwen3 = any("qwen3" in m for m in models)
            has_coder = any("qwen2.5-coder" in m for m in models)
            print(f"4. Ollama Local LLM: Online ({len(models)} models available) {check_mark(True)}")
            print(f"   - qwen3:1.7b (Scriptwriting): {'Installed' if has_qwen3 else 'Missing'} {check_mark(has_qwen3)}")
            print(f"   - qwen2.5-coder:3b (Code Analysis): {'Installed' if has_coder else 'Missing'} {check_mark(has_coder)}")
            if not has_qwen3:
                all_passed = False
    except Exception as e:
        print(f"4. Ollama Local LLM: Offline at http://127.0.0.1:11434 ({e}) {check_mark(False)}")
        all_passed = False

    # 5. Kokoro ONNX Offline Voice
    try:
        from backend.services.tts_service import tts_service
        voices = tts_service.get_voices()
        print(f"5. Offline TTS Engine: Kokoro v1.0 ONNX ({len(voices)} voices ready) {check_mark(len(voices) > 0)}")
    except Exception as e:
        print(f"5. Offline TTS Engine: Failed ({e}) {check_mark(False)}")
        all_passed = False

    # 6. Playwright Headless Chromium
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            b.close()
        print(f"6. Headless Browser (Playwright Chromium): Available {check_mark(True)}")
    except Exception as e:
        print(f"6. Headless Browser: Error ({e}) {check_mark(False)}")
        all_passed = False

    # 7. Lemo-Opuscar Visual Styles
    try:
        from backend.services.style_service import style_service
        styles = style_service.list_styles()
        print(f"7. Lemo-Opuscar Repertoire: {len(styles)} styles indexed {check_mark(len(styles) >= 90)}")
    except Exception as e:
        print(f"7. Lemo-Opuscar Repertoire: Error ({e}) {check_mark(False)}")
        all_passed = False

    # 8. Database & Project Storage
    try:
        from backend.database.db import get_connection, init_db
        init_db()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM projects")
        count = cursor.fetchone()[0]
        conn.close()
        print(f"8. SQLite Database: Initialized & Connected ({count} projects on disk) {check_mark(True)}")
    except Exception as e:
        print(f"8. SQLite Database: Error ({e}) {check_mark(False)}")
        all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("  STATUS: ALL CHECKS PASSED — READY FOR FULL VIDEO PRODUCTION")
    else:
        print("  STATUS: SOME CHECKS FAILED — REVIEW THE ITEMS ABOVE")
    print("=" * 60)

if __name__ == "__main__":
    run()

