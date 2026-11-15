import os
import sys
import json
import time
from backend.services.project_service import project_service
from backend.services.quality_service import quality_service

def main():
    print("=" * 70)
    print("EXECUTING ACCEPTANCE TEST: NOVEMBER 2026 MICROSOFT OUTLOOK OUTAGE")
    print("Topic: The November 12–13, 2026 Microsoft Outlook / Exchange Online outage")
    print("Duration: 36s (6 distinct scenes x 6s) | Aspect: 9:16 | Voice: af_bella")
    print("=" * 70)

    t0 = time.time()
    project = project_service.create_project({
        "name": "November 2026 Microsoft Outlook Outage",
        "topic": "The November 12–13, 2026 Microsoft Outlook / Exchange Online outage: automated health check failures, traffic bottlenecks, and service restoration",
        "target_duration": 36,
        "aspect_ratio": "9:16",
        "fps": 24,
        "style_slug": "swiss-motion",
        "voice": "af_bella",
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
    print("PRODUCTION PIPELINE EXECUTION COMPLETED")
    print(f"Status: {status}")
    print(f"Elapsed Time: {t1 - t0:.2f} seconds")
    print(f"Final MP4 Video: {out_video}")
    if err:
        print(f"Error Details: {err}")
    print("=" * 70)

    project_dir = os.path.join(os.path.dirname(os.path.dirname(out_video))) if out_video else ""

    # Verify Research Deliverables
    print("\n--- 1. VERIFYING RESEARCH ARTIFACTS ---")
    research_dir = os.path.join(project_dir, "research")
    for f_name in ["research.json", "sources.json", "claims.json", "research_report.md"]:
        f_path = os.path.join(research_dir, f_name)
        exists = os.path.exists(f_path)
        sz = os.path.getsize(f_path) if exists else 0
        print(f"  [{'OK' if exists else 'FAIL'}] {f_name} ({sz} bytes)")

    # Verify Treatment & Storyboard
    print("\n--- 2. VERIFYING TREATMENT & SHOT LIST ---")
    treat_path = os.path.join(project_dir, "script", "TREATMENT.md")
    shot_path = os.path.join(project_dir, "script", "SHOT_LIST.json")
    sb_path = os.path.join(project_dir, "storyboard", "storyboard.json")
    for f_name, f_path in [("TREATMENT.md", treat_path), ("SHOT_LIST.json", shot_path), ("storyboard.json", sb_path)]:
        exists = os.path.exists(f_path)
        sz = os.path.getsize(f_path) if exists else 0
        print(f"  [{'OK' if exists else 'FAIL'}] {f_name} ({sz} bytes)")

    # Verify Audio Stems & Cues
    print("\n--- 3. VERIFYING MULTI-STEM AUDIO PRODUCTION ---")
    audio_dir = os.path.join(project_dir, "audio")
    for f_name in ["stem_voice.wav", "stem_music.wav", "stem_sfx.wav", "mix.wav", "audio_cues.json", "music_plan.json", "cues.md", "mix.py"]:
        f_path = os.path.join(audio_dir, f_name)
        exists = os.path.exists(f_path)
        sz = os.path.getsize(f_path) if exists else 0
        print(f"  [{'OK' if exists else 'FAIL'}] {f_name} ({sz} bytes)")

    # Run Strict Quality Suite
    print("\n--- 4. EXECUTING STRICT QUALITY CONTROL SUITE ---")
    if out_video and os.path.exists(out_video):
        with open(sb_path, "r", encoding="utf-8") as f:
            storyboard = json.load(f)

        qc = quality_service.run_qc_suite(
            out_video,
            target_dur=36,
            storyboard=storyboard,
            project_dir=project_dir
        )
        print(f"Overall QC Passed: {qc.get('passed')}")
        print("Detailed QC Checks:")
        print(json.dumps(qc.get("checks"), indent=2))

        # Check contact sheet
        sheet_path = os.path.join(project_dir, "renders", "contact_sheet.jpg")
        print(f"Contact Sheet: {sheet_path} ({os.path.getsize(sheet_path)} bytes)")

        if qc.get("passed"):
            print("\n>>> ACCEPTANCE TEST PASSED WITH 100% SUCCESS! <<<")
            sys.exit(0)
        else:
            print("\n>>> ACCEPTANCE TEST FAILED QC CHECKS! <<<")
            sys.exit(1)
    else:
        print("\n>>> ACCEPTANCE TEST FAILED: Output video not generated! <<<")
        sys.exit(1)

if __name__ == "__main__":
    main()

