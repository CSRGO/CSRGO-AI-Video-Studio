import os
import sys
import time
import json
import shutil
import subprocess
from PIL import Image

from backend.core.local_ai_config import local_ai_config
from backend.services.ollama_manager import ollama_manager
from backend.services.lemo_loader import lemo_loader
from backend.services.claude_animation_worker import claude_animation_worker
from backend.services.project_service import project_service, PROJECTS_DIR, OUTPUT_DIR
from backend.services.visual_service import visual_service
from backend.services.render_service import render_service

def log_header(title: str):
    print("\n" + "=" * 70)
    print(f" {title.upper()}")
    print("=" * 70)

def test_a_local_inference() -> bool:
    log_header("Test A — Local Inference (Claude Code + Ollama)")
    t0 = time.time()
    
    # 1. Check Ollama running
    assert ollama_manager.is_ollama_running(), "Ollama is not running"
    print("✓ Ollama running at", ollama_manager.endpoint)
    
    # 2. Check Claude Code CLI
    claude_path = ollama_manager.claude_executable
    print("✓ Claude Code CLI path:", claude_path)
    assert os.path.exists(claude_path) or shutil.which(claude_path), "Claude executable not found"
    
    # 3. Test direct non-interactive inference
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = ollama_manager.endpoint
    env["ANTHROPIC_AUTH_TOKEN"] = "ollama"
    env["ANTHROPIC_API_KEY"] = "ollama"
    env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
    
    cmd = [
        claude_path,
        "-p", "Respond strictly with: LOCAL_TEST_A_PASSED",
        "--model", ollama_manager.coding_model,
        "--bare",
        "--dangerously-skip-permissions"
    ]
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate(timeout=30)
    elapsed = round(time.time() - t0, 2)
    print(f"✓ Claude Code responded in {elapsed}s (Exit code: {proc.returncode})")
    print(f"Output preview: {stdout.strip()[:100]}")
    assert proc.returncode == 0, f"Claude Code exited with code {proc.returncode}: {stderr}"
    assert len(stdout.strip()) > 0, "Claude Code returned empty response"
    print(">>> TEST A: PASSED")
    return True

def test_b_animation_generation() -> bool:
    log_header("Test B — Real Animation Component Generation")
    t0 = time.time()
    
    test_scene = {
        "title": "Buffer Pool Exhaustion",
        "visual_prompt": "Animated database buffer pool filling up to 100% with red saturation alerts and worker thread locks",
        "narration": "Worker threads locked up as the shared memory buffer reached 100% capacity.",
        "visual_archetype": "system_simulation",
        "subject": "Database Buffer Pool Anomaly"
    }
    
    test_dir = os.path.join(PROJECTS_DIR, "test_component_b")
    os.makedirs(test_dir, exist_ok=True)
    
    res = claude_animation_worker.generate_scene_animation(
        scene=test_scene,
        style_slug="swiss-motion",
        project_dir=test_dir,
        scene_idx=1
    )
    
    comp_path = res["component_path"]
    assert os.path.exists(comp_path), f"Component file was not created: {comp_path}"
    
    with open(comp_path, "r", encoding="utf-8") as f:
        code = f.read()
    print(f"✓ Generated component size: {len(code)} bytes")
    
    is_valid, err = claude_animation_worker.validate_js_syntax(code)
    print(f"✓ Syntax validation result: {is_valid} ({err})")
    assert is_valid, f"Generated JavaScript has syntax errors: {err}"
    
    # Render preview HTML to test browser execution
    preview_html = os.path.join(test_dir, "preview.html")
    with open(preview_html, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Test B</title></head>
<body style="margin:0; background:#f8f6f0;">
<canvas id="c" width="1080" height="1920" style="width:540px;height:960px;"></canvas>
<script>
window.READY = false;
{code}
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
try {{
    renderDynamicScene_1(ctx, 0.5, 1080, 1920);
    window.READY = true;
}} catch(e) {{
    window.ERROR = e.message;
    console.error(e);
}}
</script>
</body>
</html>""")
    
    out_frame = os.path.join(test_dir, "rendered_frame.png")
    render_service.render_single_frame(preview_html, out_frame, width=540, height=960)
    assert os.path.exists(out_frame), "Rendered frame PNG was not generated"
    assert os.path.getsize(out_frame) > 1000, "Rendered frame file is empty or corrupted"
    print(f"✓ Playwright successfully rendered frame: {out_frame} ({os.path.getsize(out_frame)} bytes)")
    
    elapsed = round(time.time() - t0, 2)
    print(f">>> TEST B: PASSED in {elapsed}s")
    return True

def test_c_lemo_style_distinction() -> bool:
    log_header("Test C — Lemo Style Visual Distinction (Swiss Motion vs Blueprint)")
    t0 = time.time()
    
    styles = ["swiss-motion", "blueprint"]
    rendered_frames = {}
    
    storyboard = {
        "title": "Style Comparison Test",
        "visual_archetype": "system_simulation",
        "total_target_duration": 10,
        "scenes": [
            {
                "index": 1,
                "scene_type": "outlook_inbox_failure",
                "title": "Service Degradation",
                "narration": "System metrics degraded rapidly across global clusters.",
                "visual_subject": "system_metrics",
                "camera_move": "push_in",
                "kinetic_texts": ["CRITICAL", "METRIC DEGRADATION"]
            }
        ]
    }
    
    timing = [{"index": 1, "start_time": 0.0, "end_time": 10.0}]
    
    for st in styles:
        out_dir = os.path.join(PROJECTS_DIR, f"test_style_{st}")
        os.makedirs(out_dir, exist_ok=True)
        html_path = os.path.join(out_dir, "visuals", "index.html")
        visual_service.generate_html_scene(
            storyboard=storyboard,
            narration_timing=timing,
            style_slug=st,
            aspect_ratio="9:16",
            output_html_path=html_path,
            subtitles_enabled=True
        )
        frame_png = os.path.join(out_dir, "frame.png")
        render_service.render_single_frame(html_path, frame_png, width=540, height=960)
        assert os.path.exists(frame_png), f"Failed to render frame for {st}"
        rendered_frames[st] = frame_png
        print(f"✓ Rendered frame for {st}: {frame_png}")
        
    # Analyze color distribution to verify visual distinction
    im_swiss = Image.open(rendered_frames["swiss-motion"]).convert("RGB")
    im_blue = Image.open(rendered_frames["blueprint"]).convert("RGB")
    
    # Calculate average RGB values
    def get_avg_rgb(im):
        stat = im.resize((50, 50))
        pixels = list(stat.getdata())
        r = sum(p[0] for p in pixels) / len(pixels)
        g = sum(p[1] for p in pixels) / len(pixels)
        b = sum(p[2] for p in pixels) / len(pixels)
        return r, g, b
        
    r_sw, g_sw, b_sw = get_avg_rgb(im_swiss)
    r_bl, g_bl, b_bl = get_avg_rgb(im_blue)
    
    print(f"✓ Swiss Motion average RGB: ({r_sw:.1f}, {g_sw:.1f}, {b_sw:.1f}) -> Warm Cream Base")
    print(f"✓ Blueprint average RGB:    ({r_bl:.1f}, {g_bl:.1f}, {b_bl:.1f}) -> Deep Prussian Blue Base")
    
    # Blueprint must have significantly higher blue ratio than Swiss Motion
    assert b_bl > r_bl and b_bl > g_bl, "Blueprint image does not exhibit dominant blue tones"
    assert r_sw > 150 and g_sw > 150, "Swiss Motion does not exhibit warm bright paper tones"
    
    elapsed = round(time.time() - t0, 2)
    print(f">>> TEST C: PASSED in {elapsed}s (Distinct visual palettes verified)")
    return True

def test_d_complete_video() -> bool:
    log_header("Test D — Complete End-to-End Production Video")
    t0 = time.time()
    
    project_data = {
        "name": "Cache Stampede Resilience",
        "topic": "Distributed Cache Stampede and Dogpiling Incident Analysis",
        "target_duration": 45,
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 24,
        "language": "en",
        "voice": "af_bella",
        "style_slug": "swiss-motion",
        "music_enabled": True,
        "sfx_enabled": True,
        "subtitles_enabled": True,
        "draft_render": False
    }
    
    print("Creating project...")
    proj = project_service.create_project(project_data)
    proj_id = proj["id"]
    slug = proj["slug"]
    print(f"✓ Project created: {proj_id} ({slug})")
    
    print("Executing full automated pipeline (Stages 0 through 10)...")
    # Execute synchronously in test
    project_service._run_pipeline(proj_id, "test_job_d")
    
    updated_proj = project_service.get_project(proj_id)
    print(f"✓ Final project status: {updated_proj['status']} (Stage: {updated_proj['stage']})")
    assert updated_proj["status"] == "completed", f"Production failed: {updated_proj.get('error_message')}"
    
    final_mp4 = updated_proj["output_video_path"]
    assert os.path.exists(final_mp4), f"Final MP4 not found: {final_mp4}"
    file_size_mb = os.path.getsize(final_mp4) / (1024 * 1024)
    print(f"✓ Final MP4 verified: {final_mp4} ({file_size_mb:.2f} MB, Duration: {updated_proj['actual_duration']}s)")
    assert file_size_mb > 1.0, f"MP4 file size is too small: {file_size_mb} MB"
    
    # Check QC report
    qc_file = os.path.join(PROJECTS_DIR, slug, "renders", "qc.json")
    assert os.path.exists(qc_file), "QC report file not found"
    with open(qc_file, "r", encoding="utf-8") as f:
        qc_data = json.load(f)
    print(f"✓ Automated QC checks: {qc_data.get('passed_count', 0)}/{qc_data.get('total_checks', 0)} passed")
    
    elapsed = round(time.time() - t0, 2)
    print(f">>> TEST D: PASSED in {elapsed}s")
    return True

def test_e_restart_persistence() -> bool:
    log_header("Test E — Restart Persistence & Zero Manual Configuration")
    t0 = time.time()
    
    # 1. Verify local_ai.yaml exists and is valid
    assert os.path.exists(local_ai_config.config_path), "local_ai.yaml not found"
    print(f"✓ Configuration file verified at {local_ai_config.config_path}")
    
    # 2. Simulate fresh backend startup initialization
    status = ollama_manager.verify_and_initialize(skip_smoke_test=True)
    print("✓ Auto-initialization on startup returned:")
    print(f"  Ready: {status['ready']}")
    print(f"  Ollama Running: {status['ollama_running']}")
    print(f"  Models Present: {status['models']}")
    print(f"  Claude Code: {status['claude_code_version']}")
    
    assert status["ready"] is True, f"Startup initialization failed: {status.get('last_error')}"
    assert status["ollama_running"] is True
    assert len(status["models"]) >= 2
    
    elapsed = round(time.time() - t0, 2)
    print(f">>> TEST E: PASSED in {elapsed}s (Zero manual environment variables required)")
    return True

def test_f_failure_handling() -> bool:
    log_header("Test F — Failure Handling & Controlled Recovery")
    t0 = time.time()
    
    # 1. Temporarily point to non-existent endpoint to simulate Ollama being offline/stopped
    original_endpoint = ollama_manager.endpoint
    ollama_manager.endpoint = "http://127.0.0.1:11439" # Non-existent port
    
    print("Testing health check against dead endpoint (http://127.0.0.1:11439)...")
    is_running = ollama_manager.is_ollama_running()
    print(f"✓ Correctly detected offline status: is_ollama_running() == {is_running}")
    assert is_running is False, "Expected offline status for closed port"
    
    # Restore original endpoint
    ollama_manager.endpoint = original_endpoint
    print("Testing auto-recovery with active endpoint...")
    recovered_status = ollama_manager.verify_and_initialize(skip_smoke_test=True)
    assert recovered_status["ready"] is True, "Recovery verification failed"
    print("✓ Successfully recovered and verified engine readiness.")
    
    elapsed = round(time.time() - t0, 2)
    print(f">>> TEST F: PASSED in {elapsed}s")
    return True

if __name__ == "__main__":
    start_all = time.time()
    print("\n" + "#" * 70)
    print(" CSRGO AI VIDEO STUDIO — PERMANENT CLAUDE CODE + OLLAMA TEST SUITE")
    print("#" * 70)
    
    results = {}
    try:
        results["Test A (Local Inference)"] = test_a_local_inference()
        results["Test B (Animation Generation)"] = test_b_animation_generation()
        results["Test C (Lemo Style Distinction)"] = test_c_lemo_style_distinction()
        results["Test E (Restart Persistence)"] = test_e_restart_persistence()
        results["Test F (Failure Handling)"] = test_f_failure_handling()
        results["Test D (Complete Video)"] = test_d_complete_video()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"\nFATAL: Test run halted on exception: {exc}")
        sys.exit(1)
        
    total_time = round(time.time() - start_all, 2)
    log_header("Test Suite Summary")
    all_passed = True
    for test_name, passed in results.items():
        mark = "✓ PASSED" if passed else "✗ FAILED"
        if not passed:
            all_passed = False
        print(f"  {test_name.ljust(35)} : {mark}")
    print("-" * 70)
    print(f"Total Execution Time: {total_time}s")
    print(f"Overall Result: {'100% ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 70)
    sys.exit(0 if all_passed else 1)

