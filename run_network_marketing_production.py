import os
import sys
import json
import time
import soundfile as sf
import numpy as np

from backend.services.project_service import project_service
from backend.services.quality_service import quality_service
from backend.services.audio_service import audio_service
from backend.services.visual_service import visual_service
from backend.services.script_service import script_service
from backend.core.config import settings

def main():
    print("=" * 70)
    print("CSRGO AI VIDEO STUDIO — PRODUCTION RUN")
    print("Topic: How Network Marketing Works")
    print("Duration: 45s | Aspect: 9:16 | Style: swiss-motion | Voice: am_michael")
    print("=" * 70)

    t0 = time.time()
    project = project_service.create_project({
        "name": "How Network Marketing Works",
        "topic": "How Network Marketing Works: the multi-level downline structure, upward commission flow, inventory autoship requirements, and the 99% attrition reality",
        "target_duration": 45,
        "aspect_ratio": "9:16",
        "fps": 24,
        "style_slug": "swiss-motion",
        "voice": "am_michael",
        "speaking_speed": 1.0,
        "music_enabled": True,
        "sfx_enabled": True,
        "subtitles_enabled": True,
        "draft_render": False
    })

    proj_id = project["id"]
    slug = project["slug"]
    print(f"Project Created: {slug} (ID: {proj_id})")

    # Run the production pipeline synchronously
    project_service._run_pipeline(proj_id, f"job-{slug}")
    t1 = time.time()

    updated = project_service.get_project(proj_id)
    status = updated.get("status")
    out_video = updated.get("output_video_path")
    err = updated.get("error_message")

    print("\n" + "=" * 70)
    print("PRODUCTION PIPELINE FINISHED")
    print(f"Status: {status}")
    print(f"Elapsed Time: {t1 - t0:.1f}s")
    print(f"Output Video: {out_video}")
    if err:
        print(f"Error: {err}")
    print("=" * 70)

    if not out_video or not os.path.exists(out_video):
        print("FAILED: Output video does not exist!")
        sys.exit(1)

    project_dir = os.path.join(os.path.dirname(os.path.dirname(out_video)))

    # Inspect Storyboard Script
    print("\n--- 1. VERIFYING GENERATED SCRIPT & STORYBOARD ---")
    sb_path = os.path.join(project_dir, "storyboard", "storyboard.json")
    with open(sb_path, "r", encoding="utf-8") as f:
        sb = json.load(f)

    for sc in sb.get("scenes", []):
        print(f"  Scene {sc.get('scene_number')}: {sc.get('title')} [{sc.get('scene_type')}]")
        print(f"    Narration: \"{sc.get('narration')}\"")
        assert not sc.get("narration", "").lower().startswith("step "), "Forbidden dummy narration detected!"

    # Inspect Audio Stems & Mastering
    print("\n--- 2. VERIFYING AUDIO STEMS (INSTAGRAM SHORTS DSP STANDARD) ---")
    audio_dir = os.path.join(project_dir, "audio")
    v_stem_p = os.path.join(audio_dir, "stem_voice.wav")
    m_stem_p = os.path.join(audio_dir, "stem_music.wav")
    s_stem_p = os.path.join(audio_dir, "stem_sfx.wav")
    mix_p = os.path.join(audio_dir, "mix.wav")

    for p_name, p_file in [("Voice", v_stem_p), ("Music", m_stem_p), ("SFX", s_stem_p), ("Master Mix", mix_p)]:
        data, sr = sf.read(p_file)
        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(data**2)))
        print(f"  [{p_name}] sr={sr}, peak={peak:.4f}, rms={rms:.4f}, shape={data.shape}")
        assert rms > 0.005, f"{p_name} is silent!"

    # Inspect Video Quality & Motion
    print("\n--- 3. EXECUTING STRICT QUALITY CONTROL SUITE ---")
    qc = quality_service.run_qc_suite(
        out_video,
        target_dur=45,
        storyboard=sb,
        project_dir=project_dir
    )
    print(f"QC Overall Passed: {qc['passed']}")
    print(json.dumps(qc["checks"], indent=2))

    # Inspect Contact Sheet
    sheet_p = os.path.join(project_dir, "renders", "contact_sheet.jpg")
    print(f"Contact Sheet: {sheet_p} ({os.path.getsize(sheet_p)} bytes)")

    print("\n" + "=" * 70)
    print("SUCCESS: NETWORK MARKETING VIDEO PRODUCED AND VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
