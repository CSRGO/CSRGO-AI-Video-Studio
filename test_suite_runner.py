import os
import sys
import json
import time
from backend.services.project_service import project_service
from backend.services.quality_service import quality_service

def run_test(name: str, topic: str, target_dur: int, style: str, voice: str):
    print(f"\n======================================================================")
    print(f"STARTING ACCEPTANCE TEST: {name}")
    print(f"Topic: {topic}")
    print(f"Style: {style} | Voice: {voice} | Target Duration: {target_dur}s")
    print(f"======================================================================")

    t0 = time.time()
    project = project_service.create_project({
        "name": name,
        "topic": topic,
        "target_duration": target_dur,
        "aspect_ratio": "9:16",
        "fps": 24,
        "style_slug": style,
        "voice": voice,
        "speaking_speed": 1.0,
        "music_enabled": True,
        "sfx_enabled": True,
        "subtitles_enabled": True,
        "draft_render": False
    })

    proj_id = project["id"]
    slug = project["slug"]
    print(f"Created project: {slug} (ID: {proj_id})")

    # Run the pipeline synchronously
    project_service._run_pipeline(proj_id, f"job-{slug}")
    t1 = time.time()

    updated = project_service.get_project(proj_id)
    status = updated.get("status")
    out_video = updated.get("output_video_path")
    err = updated.get("error_message")

    print(f"\n--- TEST RESULT FOR: {name} ---")
    print(f"Status: {status}")
    print(f"Elapsed Time: {t1 - t0:.2f}s")
    print(f"Output Video: {out_video}")
    if err:
        print(f"Error: {err}")

    if out_video and os.path.exists(out_video):
        # Inspect video
        probe = quality_service.inspect_video(out_video)
        print(f"Probe: Duration={probe.get('duration')}s, Res={probe.get('width')}x{probe.get('height')}, FPS={probe.get('fps')}, Audio={probe.get('has_audio')}")
        
        # Load storyboard for visual diversity check
        storyboard_path = os.path.join(os.path.dirname(os.path.dirname(out_video)), "storyboard", "storyboard.json")
        storyboard = None
        if os.path.exists(storyboard_path):
            with open(storyboard_path, "r", encoding="utf-8") as f:
                storyboard = json.load(f)

        qc = quality_service.run_qc_suite(out_video, target_dur=target_dur, storyboard=storyboard)
        print(f"QC Suite Passed: {qc.get('passed')}")
        print("QC Checks:", json.dumps(qc.get("checks"), indent=2))
        return {
            "name": name,
            "status": status,
            "passed": qc.get("passed", False),
            "duration": probe.get("duration"),
            "resolution": f"{probe.get('width')}x{probe.get('height')}",
            "fps": probe.get("fps"),
            "video_path": out_video,
            "checks": qc.get("checks")
        }
    else:
        return {
            "name": name,
            "status": status,
            "passed": False,
            "error": err
        }

if __name__ == "__main__":
    test_arg = sys.argv[1] if len(sys.argv) > 1 else "A"
    
    if test_arg == "A":
        res = run_test(
            name="Acceptance Test A - Git Internals",
            topic="How Git works behind the scenes: staging files, cryptographic SHA-1 hashes, commit snapshots, and branch DAG traversal",
            target_dur=24,
            style="swiss-motion",
            voice="af_bella"
        )
        print("\nSUMMARY RESULT:", json.dumps(res, indent=2))
    elif test_arg == "B":
        res = run_test(
            name="Acceptance Test B - AI Agent Tool Use",
            topic="How AI agents use tools to complete tasks: prompt planning, tool routing, browser DOM inspection, and verification loops",
            target_dur=24,
            style="neon-tubes",
            voice="am_michael"
        )
        print("\nSUMMARY RESULT:", json.dumps(res, indent=2))
    elif test_arg == "C":
        res = run_test(
            name="Acceptance Test C - Neural Network Learning",
            topic="How neural networks learn: forward signal propagation, loss calculation, and backpropagation gradient descent",
            target_dur=24,
            style="blueprint",
            voice="af_sarah"
        )
        print("\nSUMMARY RESULT:", json.dumps(res, indent=2))

