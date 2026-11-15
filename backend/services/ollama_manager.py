import os
import shutil
import subprocess
import time
import urllib.request
import urllib.error
import json
from typing import Dict, Any, List, Optional
from backend.core.local_ai_config import local_ai_config

class OllamaManager:
    def __init__(self):
        self.endpoint = local_ai_config.ollama_endpoint
        self.coding_model = local_ai_config.coding_model
        self.planning_model = local_ai_config.planning_model
        self.claude_executable = self._find_claude_path()
        self._state: Dict[str, Any] = {
            "ready": False,
            "ollama_running": False,
            "models_present": [],
            "inference_verified": False,
            "claude_code_installed": False,
            "claude_code_version": None,
            "claude_smoke_tested": False,
            "last_error": None,
            "checked_at": None
        }

    def _find_claude_path(self) -> str:
        # First check PATH
        which_path = shutil.which("claude")
        if which_path:
            return which_path
        # Windows default local user path
        local_user_claude = os.path.expandvars(r"%USERPROFILE%\.local\bin\claude.exe")
        if os.path.exists(local_user_claude):
            return local_user_claude
        return "claude"

    def is_ollama_running(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start_ollama_service(self, timeout_sec: int = 15) -> bool:
        if self.is_ollama_running():
            return True

        ollama_bin = shutil.which("ollama") or "ollama"
        try:
            # Launch ollama serve in background
            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)

            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags
            )
        except Exception as e:
            self._state["last_error"] = f"Failed to start Ollama subprocess: {e}"
            return False

        # Wait for API readiness
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            if self.is_ollama_running():
                return True
            time.sleep(0.5)

        self._state["last_error"] = f"Ollama failed to respond at {self.endpoint} within {timeout_sec}s"
        return False

    def list_available_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = []
                for item in data.get("models", []):
                    m_name = item.get("name") or item.get("model")
                    if m_name:
                        models.append(m_name)
                return models
        except Exception as e:
            self._state["last_error"] = f"Failed to query Ollama models: {e}"
            return []

    def verify_models(self, required_models: Optional[List[str]] = None) -> bool:
        if required_models is None:
            required_models = [self.coding_model, self.planning_model]

        available = self.list_available_models()
        self._state["models_present"] = available

        missing = []
        for req in required_models:
            # Check for exact match or prefix match (e.g., qwen2.5-coder:3b vs qwen2.5-coder:3b-instruct)
            match = any(m == req or m.startswith(req.split(":")[0]) for m in available)
            if not match:
                missing.append(req)

        if missing:
            self._state["last_error"] = f"Missing required Ollama model(s): {', '.join(missing)}"
            return False
        return True

    def verify_inference(self, model: Optional[str] = None) -> bool:
        target_model = model or self.coding_model
        try:
            data = json.dumps({
                "model": target_model,
                "prompt": "Respond with the word OK",
                "stream": False,
                "options": {"num_predict": 5}
            }).encode()
            req = urllib.request.Request(
                f"{self.endpoint}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                res_obj = json.loads(resp.read().decode())
                response_text = res_obj.get("response", "").strip()
                if response_text:
                    self._state["inference_verified"] = True
                    return True
                else:
                    self._state["last_error"] = f"Inference test returned empty output for {target_model}"
                    return False
        except Exception as e:
            self._state["last_error"] = f"Inference verification failed for {target_model}: {e}"
            return False

    def verify_claude_code_installation(self) -> bool:
        try:
            cmd = [self.claude_executable, "--version"]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=5)
            if res.returncode == 0:
                self._state["claude_code_installed"] = True
                self._state["claude_code_version"] = res.stdout.strip()
                return True
            else:
                self._state["last_error"] = f"Claude CLI returned non-zero code {res.returncode}: {res.stderr}"
                return False
        except Exception as e:
            self._state["last_error"] = f"Claude Code CLI not found or failed to execute: {e}"
            return False

    def run_claude_smoke_test(self, model: Optional[str] = None) -> bool:
        target_model = model or self.coding_model
        env = os.environ.copy()
        env["ANTHROPIC_BASE_URL"] = self.endpoint
        env["ANTHROPIC_AUTH_TOKEN"] = "ollama"
        env["ANTHROPIC_API_KEY"] = "ollama"
        env["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"

        cmd = [
            self.claude_executable,
            "-p", "Print the exact word: OLLAMA_CLAUDE_VERIFIED",
            "--model", target_model,
            "--bare",
            "--dangerously-skip-permissions"
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, encoding="utf-8"
            )
            stdout, stderr = proc.communicate(timeout=25)
            if proc.returncode == 0 and len(stdout.strip()) > 0:
                self._state["claude_smoke_tested"] = True
                return True
            else:
                self._state["last_error"] = f"Claude smoke test failed (exit {proc.returncode}): {stderr or stdout}"
                return False
        except subprocess.TimeoutExpired:
            proc.kill()
            self._state["last_error"] = "Claude smoke test timed out after 25s"
            return False
        except Exception as e:
            self._state["last_error"] = f"Claude smoke test exception: {e}"
            return False

    def verify_and_initialize(self, skip_smoke_test: bool = False) -> Dict[str, Any]:
        """Runs the complete 8-step verification pipeline."""
        self._state["checked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._state["ready"] = False
        self._state["last_error"] = None

        # Step 1 & 2: Check & auto-start Ollama
        if not self.is_ollama_running():
            print("[OllamaManager] Ollama not running. Attempting to start service...")
            if not self.start_ollama_service():
                return self.get_status()

        self._state["ollama_running"] = True

        # Step 3 & 4: Verify models exist
        if not self.verify_models():
            return self.get_status()

        # Step 5: Verify inference
        if not self.verify_inference():
            return self.get_status()

        # Step 6: Verify Claude Code is installed
        if not self.verify_claude_code_installation():
            return self.get_status()

        # Step 7: Claude smoke test
        if not skip_smoke_test:
            if not self.run_claude_smoke_test():
                return self.get_status()
        else:
            self._state["claude_smoke_tested"] = True

        # Step 8: Mark ready
        self._state["ready"] = True
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        return {
            "ready": self._state["ready"],
            "ollama_running": self._state["ollama_running"],
            "models": self._state["models_present"],
            "inference_verified": self._state["inference_verified"],
            "claude_code_installed": self._state["claude_code_installed"],
            "claude_code_version": self._state["claude_code_version"],
            "claude_smoke_tested": self._state["claude_smoke_tested"],
            "last_error": self._state["last_error"],
            "checked_at": self._state["checked_at"],
            "endpoint": self.endpoint,
            "coding_model": self.coding_model
        }

ollama_manager = OllamaManager()

