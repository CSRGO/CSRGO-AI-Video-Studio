from backend.services.visual_service import visual_service
from backend.services.style_service import style_service
from playwright.sync_api import sync_playwright
import os

scenes = [
    {"scene_number": 1, "scene_type": "outlook_inbox_failure", "title": "Inbox Failure", "narration": "Millions of users opened Outlook and discovered their inboxes were not loading."},
    {"scene_number": 2, "scene_type": "m365_service_impact", "title": "Service Impact", "narration": "Exchange Online dropped offline, cascading across Microsoft 365 services."},
    {"scene_number": 3, "scene_type": "incident_scope_timeline", "title": "Incident Timeline", "narration": "Reports spiked worldwide on Downdetector at 18:00 UTC."},
    {"scene_number": 4, "scene_type": "infrastructure_bottleneck", "title": "Bottleneck", "narration": "A cluster of servers failed health checks, crushing remaining nodes."},
    {"scene_number": 5, "scene_type": "service_recovery_flow", "title": "Staged Recovery", "narration": "Engineers rerouted traffic and rebooted nodes in staged batches."},
    {"scene_number": 6, "scene_type": "cloud_resilience_takeaway", "title": "Takeaways", "narration": "The incident reveals the vital takeaways for cloud resilience."}
]

storyboard = {
    "title": "Microsoft Outlook Outage",
    "visual_archetype": "microsoft_outage_investigation",
    "scenes": scenes,
    "total_target_duration": 60
}

os.makedirs("output/style_tests", exist_ok=True)

# 1. Test Swiss Motion Style
path_swiss = "output/style_tests/test_swiss.html"
visual_service.generate_html_scene(storyboard, [], "swiss-motion", "9:16", path_swiss)
assert os.path.exists(path_swiss)
print("Swiss Motion HTML generated:", os.path.getsize(path_swiss), "bytes")

# 2. Test Blueprint Style
path_blueprint = "output/style_tests/test_blueprint.html"
visual_service.generate_html_scene(storyboard, [], "blueprint", "9:16", path_blueprint)
assert os.path.exists(path_blueprint)
print("Blueprint HTML generated:", os.path.getsize(path_blueprint), "bytes")

# 3. Test Playwright Chromium Rendering for both
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    
    # Test Swiss
    page.goto("file:///" + os.path.abspath(path_swiss).replace("\\", "/"))
    page.wait_for_function("() => window.READY === true", timeout=5000)
    page.evaluate("window.render(0.5)")
    page.screenshot(path="output/style_tests/frame_swiss.jpg", quality=90)
    print("Rendered Swiss Frame [OK]")

    # Test Blueprint
    page.goto("file:///" + os.path.abspath(path_blueprint).replace("\\", "/"))
    page.wait_for_function("() => window.READY === true", timeout=5000)
    page.evaluate("window.render(0.5)")
    page.screenshot(path="output/style_tests/frame_blueprint.jpg", quality=90)
    print("Rendered Blueprint Frame [OK]")

    browser.close()

# 4. Compare pixels of both rendered frames to prove material visual difference
from PIL import Image
import numpy as np

img_swiss = Image.open("output/style_tests/frame_swiss.jpg")
img_blue = Image.open("output/style_tests/frame_blueprint.jpg")

arr_s = np.array(img_swiss, dtype=np.float32)
arr_b = np.array(img_blue, dtype=np.float32)

diff = np.mean(np.abs(arr_s - arr_b))
print(f"Mean pixel difference between Swiss Motion and Blueprint: {diff:.2f}")
assert diff > 40.0, "Styles must produce materially different visual outputs!"
print(">>> DUAL STYLE AUTOMATED TEST PASSED WITH HIGH VISUAL DISTINCTION! <<<")

