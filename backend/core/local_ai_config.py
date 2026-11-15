import os
import yaml
from typing import Dict, Any

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "local_ai.yaml"))

DEFAULT_CONFIG: Dict[str, Any] = {
    "ai": {
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "local_only": True,
        "planning_model": "qwen3:1.7b",
        "coding_model": "qwen2.5-coder:3b"
    },
    "claude_code": {
        "enabled": True,
        "mandatory": True,
        "execution_mode": "subprocess",
        "auto_initialize": True,
        "auto_repair": True,
        "max_repair_attempts": 3,
        "timeout_seconds": 45,
        "executable": "claude"
    },
    "production": {
        "use_selected_lemo_skill": True,
        "dynamic_scene_generation": True,
        "narration_driven_timeline": True,
        "scene_specific_audio": True,
        "visual_quality_checks": True
    }
}

class LocalAIConfig:
    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                # Merge loaded over default
                merged = DEFAULT_CONFIG.copy()
                for section in ("ai", "claude_code", "production"):
                    if section in loaded and isinstance(loaded[section], dict):
                        merged[section] = {**DEFAULT_CONFIG.get(section, {}), **loaded[section]}
                self._data = merged
            except Exception as e:
                print(f"[LocalAIConfig] Warning: Failed to parse {self.config_path}: {e}. Using defaults.")
                self._data = DEFAULT_CONFIG.copy()
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()
        return self._data

    def save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._data, f, default_flow_style=False, sort_keys=False)

    @property
    def ai(self) -> Dict[str, Any]:
        return self._data.get("ai", {})

    @property
    def claude_code(self) -> Dict[str, Any]:
        return self._data.get("claude_code", {})

    @property
    def production(self) -> Dict[str, Any]:
        return self._data.get("production", {})

    @property
    def ollama_endpoint(self) -> str:
        return self.ai.get("endpoint", "http://127.0.0.1:11434")

    @property
    def coding_model(self) -> str:
        return self.ai.get("coding_model", "qwen2.5-coder:3b")

    @property
    def planning_model(self) -> str:
        return self.ai.get("planning_model", "qwen3:1.7b")

local_ai_config = LocalAIConfig()

