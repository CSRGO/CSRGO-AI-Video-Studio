"""Claude Code generation via native Ollama or FreeLLMAPI Anthropic Messages.

Unified API keys stay in backend memory/environment, never project files.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
from dotenv import load_dotenv
load_dotenv(ROOT / '.env', override=False)
CONFIG_PATH = ROOT / '.env.ai.local'
DEFAULTS = {
    'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
    'planning_model': 'qwen3:1.7b', 'coding_model': 'qwen2.5-coder:3b',
    'api_key_env': 'FREELLMAPI_API_KEY', 'timeout_seconds': 180,
}
_snapshot = ContextVar('ai_snapshot', default=None)


def parse_json(text):
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S).strip()
    match = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except (ValueError, TypeError) as exc:
        raise RuntimeError('Claude Code returned invalid JSON; generation stopped rather than inventing a fallback.') from exc


class AIService:
    def __init__(self, config_path=CONFIG_PATH):
        self.path = Path(config_path)
        self.lock = threading.RLock()
        self.active = 0
        self._session_key = None
        self._config = dict(DEFAULTS)
        if self.path.exists():
            self._config.update(json.loads(self.path.read_text(encoding='utf-8')))

    def config(self):
        return copy.deepcopy(_snapshot.get() or self._config)

    def public_config(self):
        cfg = self.config()
        cfg['api_key_present'] = bool(self._session_key or os.environ.get(cfg['api_key_env']))
        cfg['claude_installed'] = bool(self.claude_path())
        cfg['engine'] = 'Claude Code'
        return cfg

    def update(self, data):
        with self.lock:
            if self.active:
                raise ValueError('Wait for active productions to finish before switching models.')
            cfg = {**self._config, **data}
            if cfg['provider'] not in ('ollama', 'freellmapi'):
                raise ValueError('Choose Ollama or FreeLLMAPI.')
            from urllib.parse import urlsplit, urlunsplit
            url = urlsplit(cfg['endpoint'].strip())
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Enter an HTTP(S) endpoint without credentials, query or fragment.')
            path = url.path.rstrip('/')
            if cfg['provider'] == 'freellmapi' and path.endswith('/v1'):
                path = path[:-3]
            cfg['endpoint'] = urlunsplit((url.scheme, url.netloc, path, '', ''))
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', cfg['api_key_env']):
                raise ValueError('API key environment variable name is invalid.')
            if not all(isinstance(cfg[f], str) and 0 < len(cfg[f]) <= 200 for f in ('planning_model', 'coding_model')):
                raise ValueError('Both model names are required (maximum 200 characters).')
            cfg['timeout_seconds'] = max(30, min(600, int(cfg['timeout_seconds'])))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
            tmp.replace(self.path)
            self._config = cfg
            return self.public_config()

    @contextmanager
    def production(self):
        with self.lock:
            self.active += 1
            cfg = self.config()
        token = _snapshot.set(cfg)
        try:
            yield cfg
        finally:
            _snapshot.reset(token)
            with self.lock:
                self.active -= 1

    def claude_path(self):
        return shutil.which('claude') or next((str(p) for p in [
            Path('/workspace/cloud-tools/node_modules/.bin/claude'),
            Path.home() / '.local/bin/claude', Path.home() / '.local/bin/claude.exe',
        ] if p.is_file()), None)

    def check_ready(self):
        cfg = self.config()
        if not self.claude_path():
            raise RuntimeError('Claude Code CLI is missing. Install @anthropic-ai/claude-code and put claude on PATH.')
        if cfg['provider'] == 'freellmapi':
            if not (self._session_key or os.environ.get(cfg['api_key_env'])):
                raise RuntimeError(f"Enter your FreeLLMAPI unified key in Models & Settings, or set {cfg['api_key_env']} in the backend environment.")
            if not self.list_models()['models']:
                raise RuntimeError('No available FreeLLMAPI models. Enable a provider and model in your desktop app.')
        else:
            try:
                with httpx.Client(timeout=8) as client:
                    res = client.get(cfg['endpoint'].rstrip('/') + '/api/tags')
                    res.raise_for_status()
                    names = {m['name'] for m in res.json().get('models', [])}
                missing = {cfg['planning_model'], cfg['coding_model']} - names
                if missing:
                    raise RuntimeError('Pull these Ollama models first: ' + ', '.join(sorted(missing)))
            except httpx.HTTPError as exc:
                raise RuntimeError('Ollama is unavailable. Start ollama serve or select FreeLLMAPI in Model settings.') from exc
        return self.public_config()

    def generate(self, prompt, model=None, system=None, purpose='planning'):
        cfg = self.config()
        executable = self.claude_path()
        if not executable:
            raise RuntimeError('Claude Code CLI is not installed.')
        selected = cfg['coding_model'] if purpose == 'coding' else cfg['planning_model']
        env = os.environ.copy()
        # Avoid inheriting unrelated cloud credentials or Claude sessions.
        for key in list(env):
            if key.startswith(('ANTHROPIC_', 'CLAUDE_CODE_')) or key == 'CLAUDECODE':
                env.pop(key, None)
        env.update({'ENABLE_CLAUDEAI_MCP_SERVERS': 'false', 'DISABLE_NONESSENTIAL_TRAFFIC': '1',
                    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'})
        env['ANTHROPIC_BASE_URL'] = cfg['endpoint']
        env['ANTHROPIC_AUTH_TOKEN'] = (self._session_key or os.environ.get(cfg['api_key_env'], '')) if cfg['provider'] == 'freellmapi' else 'ollama'
        if cfg['provider'] == 'freellmapi' and not env['ANTHROPIC_AUTH_TOKEN']:
            raise RuntimeError('Enter your FreeLLMAPI unified key in Models & Settings.')
        # FreeLLMAPI explicitly requires Bearer auth, with ANTHROPIC_API_KEY unset.
        # Tool-free generation writes text; it cannot modify the checkout.
        cmd = [executable, '-p', '--model', selected, '--bare', '--tools', '',
               '--no-session-persistence', '--output-format', 'text', '--permission-mode', 'dontAsk']
        full_prompt = ((system + '\n\n') if system else '') + prompt
        try:
            result = subprocess.run(cmd, input=full_prompt, env=env, cwd=str(ROOT),
                capture_output=True, text=True, encoding="utf-8", timeout=cfg['timeout_seconds'])
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Claude Code timed out after {cfg['timeout_seconds']} seconds.") from exc
        if result.returncode or not result.stdout.strip():
            raise RuntimeError('Claude Code generation failed. Check provider connectivity, credentials, model availability and limits.')
        return re.sub(r'<think>.*?</think>', '', result.stdout, flags=re.S).strip()

    def chat(self, messages, model=None):
        return self.generate(json.dumps(messages, ensure_ascii=False))

    def list_models(self):
        cfg = self.config()
        if cfg['provider'] == 'freellmapi':
            key = self._session_key or os.environ.get(cfg['api_key_env'], '')
            if not key:
                raise RuntimeError('Enter your FreeLLMAPI unified key first.')
            try:
                with httpx.Client(timeout=15) as client:
                    response = client.get(cfg['endpoint'].rstrip('/') + '/v1/models',
                        params={'available': 'true'}, headers={'Authorization': 'Bearer ' + key})
                    response.raise_for_status()
                return {'models': [{'model': m['id'], 'name': m.get('name', m['id'])}
                                   for m in response.json().get('data', [])]}
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f'FreeLLMAPI returned HTTP {exc.response.status_code}. Check your unified key and enabled models.') from exc
            except httpx.HTTPError as exc:
                raise RuntimeError('Cannot reach FreeLLMAPI. Start the desktop app on the same machine as the studio backend, or use a reachable server URL.') from exc
        with httpx.Client(timeout=8) as client:
            response = client.get(cfg['endpoint'].rstrip('/') + '/api/tags')
            response.raise_for_status()
        return response.json()

ai_service = AIService()
