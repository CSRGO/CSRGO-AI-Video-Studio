"""Reproduce legacy Windows code-page defaults without requiring Windows."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.ai_service import AIService
from backend.services.claude_animation_worker import ClaudeAnimationWorker
from backend.services.framework_service import framework_service

TEXT = 'Research → script → narration — नमस्ते 世界 🎬'
ECHO = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())']


class UnicodeProcessTests(unittest.TestCase):
    def test_legacy_encoding_reproduces_reported_failure(self):
        with patch('subprocess._text_encoding', return_value='cp1252'):
            with self.assertRaises(UnicodeEncodeError):
                subprocess.run(ECHO, input=TEXT, text=True, capture_output=True, timeout=10)

    def test_claude_prompt_and_response_preserve_unicode_under_legacy_locale(self):
        real_run = subprocess.run
        def echo_claude(command, **kwargs):
            self.assertEqual(kwargs.get('encoding'), 'utf-8')
            return real_run(ECHO, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            service = AIService(Path(directory)/'settings.json')
            service._config['provider'] = 'ollama'
            with patch.object(service, 'claude_path', return_value='claude'), \
                 patch('subprocess._text_encoding', return_value='cp1252'), \
                 patch('backend.services.ai_service.subprocess.run', side_effect=echo_claude):
                self.assertEqual(service.generate(TEXT), TEXT)

    def test_javascript_validation_preserves_unicode_source(self):
        with patch('subprocess._text_encoding', return_value='cp1252'):
            valid, error = ClaudeAnimationWorker().validate_js_syntax('const caption = '+json.dumps(TEXT,ensure_ascii=False)+';')
        self.assertTrue(valid, error)

    def test_renderer_progress_and_diagnostics_decode_utf8(self):
        payload = json.dumps({'progress':50, 'caption':TEXT}, ensure_ascii=False)
        command = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write('+repr(payload.encode('utf-8'))+')']
        progress = []
        with patch('subprocess._text_encoding', return_value='cp1252'):
            output = framework_service._run(command, str(Path.cwd()), os.environ.copy(),
                progress_cb=lambda *args: progress.append(args), timeout=10)
        self.assertEqual(json.loads(output)['caption'], TEXT)
        self.assertEqual(len(progress), 1)


if __name__ == '__main__':
    unittest.main()
