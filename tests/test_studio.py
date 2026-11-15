import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from backend.services.ai_service import AIService, DEFAULTS, parse_json
from backend.services.research_service import ResearchService
from backend.services.script_service import ScriptService
from backend.services.claude_animation_worker import ClaudeAnimationWorker
from backend.services.visual_service import VisualService
from backend.services.render_service import RenderService
from backend.services.quality_service import QualityService
from backend.core.config import settings
from backend.database.db import init_db, get_connection
from backend.services.project_service import ProjectService

SOURCE = {'source_id': 'SRC-01', 'title': 'Email explanation', 'url': 'https://example.com/article',
          'extracted_text': 'Outlook is an email application. When a mail server is unavailable, messages cannot be synchronized.'}
CLAIM = {'claim_text': 'Outlook is an email application.',
         'evidence': [{'source_id': 'SRC-01', 'quote': 'Outlook is an email application.'}]}


class ResearchTests(unittest.TestCase):
    def test_event_identity_never_invents_incident_date(self):
        service = ResearchService()
        first = service.detect_event_identity('Outlook outage January 2023')
        self.assertNotIn('2026', json.dumps(first))
        self.assertEqual(first, service.detect_event_identity('Outlook outage January 2023'))
        self.assertNotEqual(first['event_id'], service.detect_event_identity('Outlook outage 2026')['event_id'])

    def test_claim_requires_real_source_and_exact_quote(self):
        service = ResearchService()
        self.assertEqual(service.validate_claims([CLAIM], [SOURCE])[0]['status'], 'source_backed')
        for evidence in [{'source_id': 'SRC-99', 'quote': CLAIM['evidence'][0]['quote']},
                         {'source_id': 'SRC-01', 'quote': 'Invented incident details are not present in the source.'}]:
            with self.assertRaises(RuntimeError):
                service.validate_claims([{**CLAIM, 'evidence': [evidence]}], [SOURCE])

    def test_no_sources_stops_before_synthesis(self):
        with patch('backend.services.research_service.ai_service.generate', return_value='{"queries":["mail service"]}'), \
             patch.object(ResearchService, 'search_web', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'No readable research sources'):
                ResearchService().research_topic('Outlook outage')

    def test_json_does_not_fallback_to_fabricated_content(self):
        with self.assertRaises(RuntimeError):
            parse_json('not valid json')


class ScriptTests(unittest.TestCase):
    def test_story_requires_citations_and_a_duration_budget(self):
        service = ScriptService()
        scene = {'title': 'Email', 'narration': 'Outlook is an email app that synchronizes messages.',
                 'visual_subject': 'mail inbox', 'visual_description': 'A new message arrives.', 'claim_ids': ['CLM-01']}
        data = {'scenes': [copy.deepcopy(scene), copy.deepcopy(scene)]}
        research = {'claims': [{'claim_id': 'CLM-01'}]}
        validated = service.validate_storyboard(copy.deepcopy(data), research, 'Email', 10, 'blueprint', 'en')
        self.assertEqual(validated['style_slug'], 'blueprint')
        invalid = copy.deepcopy(data)
        invalid['scenes'][0]['claim_ids'] = ['CLM-99']
        with self.assertRaisesRegex(RuntimeError, 'citations'):
            service.validate_storyboard(invalid, research, 'Email', 10, 'blueprint', 'en')
        invalid = copy.deepcopy(data)
        invalid['scenes'][0]['narration'] = 'Too many words. ' * 100
        with self.assertRaisesRegex(RuntimeError, 'word count'):
            service.validate_storyboard(invalid, research, 'Email', 10, 'blueprint', 'en')

    def test_caption_rounding_carries_to_next_second(self):
        from backend.services.subtitle_service import subtitle_service
        self.assertEqual(subtitle_service._format_timestamp(59.9999), '00:01:00,000')


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = AIService(Path(self.tmp.name) / 'settings.json')

    def test_freellmapi_native_endpoint_models_and_persist_without_secrets(self):
        saved = self.service.update({'provider': 'freellmapi', 'endpoint': 'http://127.0.0.1:31415/v1/',
                                     'planning_model': 'auto', 'coding_model': 'example-coder'})
        self.assertEqual(saved['endpoint'], 'http://127.0.0.1:31415')
        self.assertEqual(saved['engine'], 'Claude Code')
        self.assertEqual(AIService(self.service.path).config()['provider'], 'freellmapi')
        self.service._session_key = 'test-secret-do-not-persist'
        self.assertNotIn('test-secret', self.service.path.read_text())
        self.assertNotIn('test-secret', json.dumps(self.service.public_config()))

    def test_production_freezes_model_selection(self):
        with self.service.production():
            with self.assertRaises(ValueError):
                self.service.update({'planning_model': 'another-model'})
        self.service.update({'planning_model': 'another-model'})

    def test_generation_uses_tool_free_claude_for_planning_and_code(self):
        with patch.object(self.service, 'claude_path', return_value='claude'), \
             patch('backend.services.ai_service.subprocess.run', return_value=Mock(returncode=0, stdout='valid output')) as run:
            self.service.generate('plan')
            self.assertEqual(run.call_args.args[0][run.call_args.args[0].index('--model')+1], DEFAULTS['planning_model'])
            self.service.generate('animation', purpose='coding')
            cmd = run.call_args.args[0]
            self.assertEqual(cmd[cmd.index('--model')+1], DEFAULTS['coding_model'])
            self.assertEqual(cmd[cmd.index('--tools')+1], '')
            self.assertNotIn('--dangerously-skip-permissions', cmd)
            self.assertEqual(run.call_args.kwargs['input'], 'animation')

    def test_native_freellmapi_contract_with_real_claude_process(self):
        from fake_anthropic import native_provider
        if not self.service.claude_path():
            self.skipTest('Claude Code CLI is not installed')
        with native_provider() as (endpoint, requests):
            self.service.update({'provider': 'freellmapi', 'endpoint': endpoint,
                                 'planning_model': 'auto', 'coding_model': 'example-coder', 'timeout_seconds': 30})
            self.service._session_key = 'test-unified-key'
            self.assertEqual(self.service.list_models()['models'][0]['model'], 'auto')
            result = self.service.generate('Reply with NATIVE_FREELLMAPI_CONTRACT_PASSED', purpose='coding')
            self.assertIn('NATIVE_FREELLMAPI_CONTRACT_PASSED', result)
            messages = [r for r in requests if '/messages' in r['path'] and 'count_tokens' not in r['path']]
            self.assertTrue(messages)
            self.assertTrue(all(r['bearer_auth'] for r in messages))
            self.assertTrue(all(not r['has_api_key_header'] for r in messages))
            self.assertEqual(messages[-1]['body']['model'], 'example-coder')



class SceneTests(unittest.TestCase):
    def test_model_failure_never_substitutes_stock_animation(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch('backend.services.claude_animation_worker.ai_service.generate', return_value='invalid javascript'):
            with self.assertRaisesRegex(RuntimeError, 'No placeholder'):
                ClaudeAnimationWorker().generate_scene_animation({'title': 'Email'}, 'blueprint', folder, 1)
            self.assertFalse((Path(folder) / 'visuals/components/scene_01.js').exists())

    def test_selected_style_context_contains_real_rules(self):
        from backend.services.lemo_loader import lemo_loader
        blueprint = lemo_loader.production_context('blueprint')
        swiss = lemo_loader.production_context('swiss-motion')
        self.assertIn('cyanotype', blueprint.lower())
        self.assertIn('SELECTED STYLE: swiss-motion', swiss)
        self.assertNotEqual(blueprint, swiss)
        with self.assertRaises(ValueError):
            lemo_loader.production_context('../README')

    def test_runtime_rejects_static_scene_and_executes_generated_component(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            components = root / 'components'
            components.mkdir()
            code = "function renderDynamicScene_1(ctx,p,W,H){ctx.fillStyle='#18336B';ctx.fillRect(0,0,W,H);ctx.fillStyle='white';ctx.fillRect(W*p/2,H/3,W/3,H/3); }"
            (components / 'scene_01.js').write_text(code)
            (components / 'scene_01.js.json').write_text(json.dumps({'engine': 'Claude Code', 'style_slug': 'blueprint'}))
            story = {'title': 'Fixture', 'total_target_duration': 2, 'scenes': [{'title': 'Email', 'narration': 'Email example', 'visual_subject': 'mail'}]}
            timing = [{'start_time': 0, 'end_time': 1.2}]
            html = str(root / 'index.html')
            VisualService().generate_html_scene(story, timing, 'blueprint', '9:16', html)
            renderer = RenderService()
            self.assertTrue(renderer.inspect_scenes(html, str(root / 'frames'))['passed'])
            (components / 'scene_01.js').write_text(code.replace('W*p/2', 'W/3'))
            VisualService().generate_html_scene(story, timing, 'blueprint', '9:16', html)
            with self.assertRaisesRegex(RuntimeError, 'no measurable animation'):
                renderer.inspect_scenes(html, str(root / 'frames'))


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.projects = root / 'projects'
        self.output = root / 'output'
        self.old_database = settings.database_url
        settings.database_url = 'sqlite:///' + str(root / 'studio.db')
        self.addCleanup(setattr, settings, 'database_url', self.old_database)
        init_db()
        self.patcher = patch.multiple('backend.services.project_service', PROJECTS_DIR=str(self.projects), OUTPUT_DIR=str(self.output))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.service = ProjectService()

    def test_delete_removes_all_owned_assets_and_jobs_only(self):
        project = self.service.create_project({'topic': 'Email testing'})
        other = self.service.create_project({'topic': 'Keep this video'})
        exported = self.output / (project['slug'] + '.mp4')
        exported.write_bytes(b'video')
        (self.output / (other['slug'] + '.mp4')).write_bytes(b'keep')
        with get_connection() as conn:
            conn.execute('INSERT INTO render_jobs (id, project_id) VALUES (?,?)', ('job1', project['id']))
        self.assertTrue(self.service.delete_project(project['slug']))
        self.assertFalse(exported.exists())
        self.assertFalse((self.projects / project['slug']).exists())
        self.assertIsNotNone(self.service.get_project(other['id']))
        self.assertTrue((self.output / (other['slug'] + '.mp4')).exists())
        with get_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM render_jobs').fetchone()[0], 0)

    def test_delete_active_job_rejected(self):
        project = self.service.create_project({'topic': 'Email'})
        self.service._active_jobs[project['id']] = {'status': 'running'}
        with self.assertRaises(ValueError):
            self.service.delete_project(project['slug'])
        self.assertIsNotNone(self.service.get_project(project['id']))

    def test_failed_qc_cannot_complete_or_export(self):
        project = self.service.create_project({'topic': 'Email', 'target_duration': 10})
        service = self.service
        import backend.services.project_service as module
        # Run the orchestrator with controlled upstream/model/media responses to isolate the completion gate.
        with patch.object(module.ai_service, 'check_ready'), \
             patch.object(module.research_service, 'research_topic', return_value={}), \
             patch.object(module.script_service, 'generate_treatment', return_value='Treatment'), \
             patch.object(module.script_service, 'generate_storyboard', return_value={'scenes': [{'title': 'Mail'}]}), \
             patch.object(module.script_service, 'generate_shot_list', return_value=[]), \
             patch.object(module.tts_service, 'synthesize_scenes', return_value=[{'start_time': 0, 'end_time': 9}]), \
             patch.object(module.subtitle_service, 'generate_srt'), \
             patch.object(module.claude_animation_worker, 'generate_all_components'), \
             patch.object(module.visual_service, 'generate_html_scene'), \
             patch.object(module.render_service, 'inspect_scenes', return_value={'passed': True}), \
             patch.object(module.audio_service, 'build_multi_stem_production', return_value={'mix_path': 'mix.wav'}), \
             patch.object(module.render_service, 'render_video_frames'), \
             patch.object(module.render_service, 'mux_video_audio'), \
             patch.object(module.render_service, 'generate_thumbnail'), \
             patch.object(module.render_service, 'generate_preview'), \
             patch.object(module.quality_service, 'generate_contact_sheet'), \
             patch.object(module.quality_service, 'run_qc_suite', return_value={'passed': False, 'checks': {'voice': False}}):
            service._run_pipeline(project['id'], 'job')
        result = service.get_project(project['id'])
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Quality checks failed', result['error_message'])
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
