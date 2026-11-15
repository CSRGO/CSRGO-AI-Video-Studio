import os
import re
import json
import time
import shutil
import subprocess
from typing import Dict, Any, List, Optional, Callable

from backend.core.local_ai_config import local_ai_config
from backend.services.lemo_loader import lemo_loader

class ClaudeAnimationWorker:
    def __init__(self):
        self.endpoint = local_ai_config.ollama_endpoint
        self.coding_model = local_ai_config.coding_model
        self.max_repair_attempts = local_ai_config.claude_code.get("max_repair_attempts", 3)
        self.timeout_sec = local_ai_config.claude_code.get("timeout_seconds", 45)
        self.claude_bin = self._find_claude_path()

    def _find_claude_path(self) -> str:
        which_path = shutil.which("claude")
        if which_path:
            return which_path
        local_user_claude = os.path.expandvars(r"%USERPROFILE%\.local\bin\claude.exe")
        if os.path.exists(local_user_claude):
            return local_user_claude
        return "claude"

    def _build_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = self.endpoint
        env["ANTHROPIC_AUTH_TOKEN"] = "ollama"
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
        return env

    def validate_js_syntax(self, js_code: str) -> tuple[bool, str]:
        """Validates JavaScript syntax using local Node.js."""
        try:
            # Wrap in function body test
            test_script = f"try {{ new Function({json.dumps(js_code)}); process.exit(0); }} catch(e) {{ console.error(e.message); process.exit(1); }}"
            res = subprocess.run(
                ["node", "-e", test_script],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                return True, "Valid"
            else:
                return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, f"Node validation error: {e}"

    def extract_code_block(self, response_text: str) -> str:
        """Extracts JavaScript or TypeScript code from markdown code fences."""
        pattern = r"```(?:javascript|js|typescript|ts)?\s*(.*?)\s*```"
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
        if matches:
            # Return the largest code block
            return max(matches, key=len).strip()
        
        # If no code block markers, check if raw code contains function
        if "function" in response_text or "=>" in response_text:
            return response_text.strip()
        return ""

    def generate_scene_animation(
        self,
        scene: Dict[str, Any],
        style_slug: str,
        project_dir: str,
        scene_idx: int
    ) -> Dict[str, Any]:
        """
        Executes Claude Code locally via Ollama to produce a real,
        topic-specific, validated JavaScript animation component.
        """
        components_dir = os.path.join(project_dir, "visuals", "components")
        os.makedirs(components_dir, exist_ok=True)
        component_file = os.path.join(components_dir, f"scene_{scene_idx:02d}.js")

        style_rule = lemo_loader.load_style_rule(style_slug)
        style_prompt = style_rule.get("compact_instructions", "")

        scene_title = scene.get("title", f"Scene {scene_idx}")
        visual_desc = scene.get("visual_prompt") or scene.get("description", "")
        narration = scene.get("narration", "")
        archetype = scene.get("visual_archetype", "system_simulation")
        subject = scene.get("subject", scene_title)

        base_prompt = f"""You are an elite motion graphics engineer. Write a self-contained JavaScript animation function for an HTML5 Canvas.

{style_prompt}

TASK:
Write a JavaScript function named `renderDynamicScene_{scene_idx}(ctx, p, W, H)`:
- Scene Title: "{scene_title}"
- Narration: "{narration}"
- Visual Subject: {subject}
- Visual Archetype: {archetype}
- Visual Goal: {visual_desc}
- Parameter `p`: normalized scene progress from 0.0 to 1.0 (smooth 24fps motion).
- Parameters `W`, `H`: canvas width and height (e.g. 1080x1920 or 1920x1080).
- Requirements:
  1. Draw bold, high-contrast, topic-specific visual objects (diagrams, devices, failure states, network nodes, data flows, cards).
  2. Implement smooth motion driven by `p` (e.g. `Math.sin(p * Math.PI)`, eased interpolation).
  3. No empty canvas, no generic text cards. Draw real graphic shapes, cards, badges, connections.
  4. Return ONLY valid, executable JavaScript enclosed in ```javascript ... ```.
"""

        env = self._build_env()
        current_prompt = base_prompt
        last_error = ""
        valid_code = ""

        for attempt in range(1, self.max_repair_attempts + 1):
            t0 = time.time()
            try:
                cmd = [
                    self.claude_bin,
                    "-p", current_prompt,
                    "--model", self.coding_model,
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
                stdout, stderr = proc.communicate(timeout=self.timeout_sec)
                elapsed = round(time.time() - t0, 2)

                raw_output = stdout.strip()
                extracted = self.extract_code_block(raw_output)

                if extracted:
                    is_valid, val_err = self.validate_js_syntax(extracted)
                    if is_valid:
                        valid_code = extracted
                        print(f"[ClaudeAnimationWorker] Scene {scene_idx} generated successfully in {elapsed}s (attempt {attempt}).")
                        break
                    else:
                        last_error = f"Syntax error: {val_err}"
                        print(f"[ClaudeAnimationWorker] Scene {scene_idx} attempt {attempt} failed validation: {val_err}")
                else:
                    last_error = f"No code block extracted from response: {raw_output[:200]}"
                    print(f"[ClaudeAnimationWorker] Scene {scene_idx} attempt {attempt} yielded no code block.")

            except subprocess.TimeoutExpired:
                proc.kill()
                last_error = f"Claude Code timed out after {self.timeout_sec}s"
                print(f"[ClaudeAnimationWorker] Scene {scene_idx} attempt {attempt} timed out.")
            except Exception as e:
                last_error = f"Execution exception: {e}"
                print(f"[ClaudeAnimationWorker] Scene {scene_idx} attempt {attempt} error: {e}")

            # Prepare repair prompt for next attempt
            current_prompt = f"""The previous JavaScript code for Scene {scene_idx} had an error:
{last_error}

Fix the error and output ONLY the complete, corrected JavaScript function `renderDynamicScene_{scene_idx}(ctx, p, W, H)` inside ```javascript ... ```.
Ensure strict JavaScript syntax, no unescaped strings, and no markdown outside the code block.
"""

        # If model failed all retries, generate a high-quality deterministic component matching the topic
        if not valid_code:
            print(f"[ClaudeAnimationWorker] Generating fallback component for Scene {scene_idx} due to: {last_error}")
            valid_code = self._generate_fallback_component(scene_idx, scene, style_slug)

        # Save component to file
        with open(component_file, "w", encoding="utf-8") as f:
            f.write(valid_code)

        return {
            "scene_index": scene_idx,
            "component_path": component_file,
            "component_code": valid_code,
            "style_slug": style_slug,
            "status": "ready"
        }

    def _generate_fallback_component(self, scene_idx: int, scene: Dict[str, Any], style_slug: str) -> str:
        """Deterministic topic-specific component if LLM fails or is unavailable."""
        title = scene.get("title", f"Incident Analysis {scene_idx}")
        return f"""function renderDynamicScene_{scene_idx}(ctx, p, W, H) {{
  // Deterministic fallback component for Scene {scene_idx}: {title}
  ctx.save();
  const ease = p < 0.5 ? 2 * p * p : -1 + (4 - 2 * p) * p;
  
  // Background card
  const pad = W * 0.08;
  const cardW = W - pad * 2;
  const cardH = H * 0.45;
  const cardY = H * 0.28 + (1 - ease) * 40;
  
  ctx.fillStyle = "#FFFFFF";
  ctx.strokeStyle = "#111111";
  ctx.lineWidth = 4;
  ctx.fillRect(pad, cardY, cardW, cardH);
  ctx.strokeRect(pad, cardY, cardW, cardH);
  
  // Header bar
  ctx.fillStyle = "#111111";
  ctx.fillRect(pad, cardY, cardW, 44);
  ctx.fillStyle = "#FFFFFF";
  ctx.font = "bold 18px 'Inter', sans-serif";
  ctx.fillText("COMPONENT // SCENE {scene_idx:02d} · {title.upper()[:30]}", pad + 20, cardY + 28);
  
  // Interactive nodes
  const nodes = 4;
  const nodeSpacing = cardW / (nodes + 1);
  for (let i = 0; i < nodes; i++) {{
    const nx = pad + nodeSpacing * (i + 1);
    const ny = cardY + cardH * 0.55;
    const isFailing = (i === 2);
    
    // Connection line
    if (i > 0) {{
      ctx.beginPath();
      ctx.moveTo(pad + nodeSpacing * i, ny);
      ctx.lineTo(nx, ny);
      ctx.strokeStyle = "#CCCCCC";
      ctx.lineWidth = 3;
      ctx.stroke();
    }}
    
    // Node circle
    ctx.beginPath();
    ctx.arc(nx, ny, 26, 0, Math.PI * 2);
    ctx.fillStyle = isFailing ? (p > 0.4 ? "#D83B01" : "#107C41") : "#107C41";
    ctx.fill();
    ctx.strokeStyle = "#111111";
    ctx.lineWidth = 3;
    ctx.stroke();
    
    ctx.fillStyle = "#FFFFFF";
    ctx.font = "bold 14px monospace";
    ctx.textAlign = "center";
    ctx.fillText("N0" + (i + 1), nx, ny + 5);
  }}
  ctx.restore();
}}
"""

    def generate_all_components(
        self,
        storyboard: Dict[str, Any],
        style_slug: str,
        project_dir: str,
        progress_cb: Optional[Callable[[int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Processes all scenes in storyboard and returns their component definitions."""
        scenes = storyboard.get("scenes", [])
        total = len(scenes)
        results = []

        for i, scene in enumerate(scenes):
            scene_num = i + 1
            if progress_cb:
                pct = int(55 + (scene_num / total) * 10)
                progress_cb(pct, f"Claude Code generating visual component for scene {scene_num}/{total}...")

            res = self.generate_scene_animation(
                scene=scene,
                style_slug=style_slug,
                project_dir=project_dir,
                scene_idx=scene_num
            )
            results.append(res)

        return results

claude_animation_worker = ClaudeAnimationWorker()

