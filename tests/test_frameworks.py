"""Framework contracts plus opt-in, real CPU export checks (explicit fixtures)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
from backend.services.framework_service import framework_service, RENDERER
from backend.services.claude_animation_worker import ClaudeAnimationWorker
from backend.services.quality_service import quality_service

REACT_SCENE = """import React from 'react';
export default function Scene({progress,width,height}){
return <div style={{position:'absolute',inset:0,background:'#18336B',color:'white'}}>
<div style={{position:'absolute',top:height*.3,left:width*(.1+.5*progress),width:width*.25,height:height*.2,background:'#e3efff'}}/>
<div style={{position:'absolute',top:height*.1,left:width*.1,fontSize:width*.06}}>EMAIL TEST FIXTURE</div></div>;
}"""
CANVAS_SCENE = """function renderDynamicScene_1(ctx,p,W,H){
ctx.fillStyle='#18336B';ctx.fillRect(0,0,W,H);ctx.fillStyle='white';ctx.fillRect(W*(.1+.5*p),H*.3,W*.25,H*.2);
ctx.font=(W*.06)+'px monospace';ctx.fillText('EMAIL TEST FIXTURE',W*.1,H*.15);
}"""


@unittest.skipUnless((RENDERER/'node_modules/remotion').exists(), 'Install renderer dependencies with npm ci --prefix renderer')
class FrameworkContractTests(unittest.TestCase):
    def test_claude_generates_native_react_using_actual_skill_and_style(self):
        with tempfile.TemporaryDirectory() as folder, patch('backend.services.claude_animation_worker.ai_service.generate',
                return_value='```jsx\n'+REACT_SCENE+'\n```') as generate:
            result = ClaudeAnimationWorker().generate_scene_animation({'title':'Email'}, 'blueprint', folder, 1, render_engine='remotion')
            self.assertEqual(result['renderer'], 'remotion')
            self.assertTrue(result['component_path'].endswith('.jsx'))
            self.assertIn('SELECTED STYLE: blueprint', generate.call_args.args[0])
            self.assertIn('useCurrentFrame()', generate.call_args.args[0])
            self.assertEqual(generate.call_args.kwargs['purpose'], 'coding')

    def test_react_scene_timers_are_rejected_not_replaced_with_canvas(self):
        with tempfile.TemporaryDirectory() as folder, patch('backend.services.claude_animation_worker.ai_service.generate',
                return_value="export default function Scene(){setTimeout(()=>{},1);return null}"):
            with self.assertRaisesRegex(RuntimeError, 'No placeholder'):
                ClaudeAnimationWorker().generate_scene_animation({'title':'Email'}, 'blueprint', folder, 1, render_engine='remotion')
            self.assertFalse((Path(folder)/'visuals/components/scene_01.jsx').exists())


@unittest.skipUnless(os.environ.get('CSRGO_TEST_NATIVE_RENDERERS') == '1', 'Set CSRGO_TEST_NATIVE_RENDERERS=1 for native export checks')
class NativeExportTests(unittest.TestCase):
    def render_fixture(self, engine):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'visuals/components').mkdir(parents=True)
            (folder/'audio').mkdir()
            sf.write(folder/'audio/mix.wav', .1*np.sin(np.arange(96000)*2*np.pi*220/48000), 48000)
            scene={'title':'Email fixture','narration':'Email moves to an inbox.', 'visual_subject':'email inbox', 'scene_number':1}
            story={'title':'Native export test fixture', 'total_target_duration':2, 'scenes':[scene]}
            timing=[{'start_time':0,'end_time':1.7}]
            ext='jsx' if engine=='remotion' else 'js'
            component=folder/f'visuals/components/scene_01.{ext}'
            component.write_text(REACT_SCENE if engine=='remotion' else CANVAS_SCENE)
            Path(str(component)+'.json').write_text(json.dumps({'engine':'Claude Code','style_slug':'blueprint','renderer':engine,'test_fixture':True}))
            manifest=framework_service.prepare(engine,story,timing,'blueprint','9:16',str(folder),draft=True,captions=False)
            output=str(folder/'native.mp4')
            with patch.dict(os.environ, {'CSRGO_RENDER_TEST':'1'}):
                framework_service.render(manifest,output)
            probe=quality_service.inspect_video(output)
            self.assertTrue(probe['valid'],probe)
            self.assertEqual((probe['width'],probe['height']), (540,960))
            self.assertAlmostEqual(probe['duration'],2,delta=.15)
            self.assertEqual(probe['fps'],24)
            self.assertTrue(quality_service.inspect_scene_motion(output,timing,2,str(folder/'frames'))['passed'])
            if engine=='hyperframes':
                report=json.loads((folder/'visuals/hyperframes/hyperframes-check.json').read_text())
                self.assertTrue(report['ok'])
                self.assertFalse(report['browserSkipped'])
                self.assertTrue(report['layout']['samples'])
                self.assertTrue(probe['has_audio'])

    def test_full_remotion_pipeline_exports_only_after_real_media_qc(self):
        from backend.core.config import settings
        from backend.database.db import init_db
        from backend.services.project_service import ProjectService
        from backend.services.ai_service import ai_service
        from backend.services.research_service import research_service
        text1 = 'Outlook is an email app that synchronizes messages with a mail server.'
        text2 = 'If the connection fails, messages cannot synchronize until service returns.'
        claims = [{'claim_text': text, 'passage_ids': [f'P{i:03d}']} for i,text in enumerate([text1,text2],1)]
        research_calls = 0
        scenes = [{'title':title,'narration':text,'claim_ids':[f'CLM-0{i}'],
                   'visual_subject':title,'visual_description':'A recognizable mailbox changes as a message moves.',
                   'emotion':'curious','sound_events':[{'progress':.5,'cue':'click','action':'mail changes'}]}
                  for i,(title,text) in enumerate([('Mailbox synchronization',text1),('Connection interrupted',text2)],1)]
        def generate(prompt, **kwargs):
            nonlocal research_calls
            if 'Create a native Remotion React scene' in prompt:
                code = REACT_SCENE if 'Mailbox synchronization' in prompt else REACT_SCENE.replace('#18336B','#264d7e').replace('EMAIL TEST FIXTURE','CONNECTION TEST FIXTURE')
                return '```jsx\n'+code+'\n```'
            if prompt.startswith('Research the exact topic'):
                research_calls += 1
                if research_calls == 1:
                    return json.dumps({'claims':[{'claim_text':text1,'evidence':[{'source_id':'SRC-01','quote':'An invalid model quotation that does not match the article.'}]}]})
                return json.dumps({'claims':claims})
            if prompt.startswith('Review these claims'):
                return json.dumps({'supported_claim_ids':['CLM-01','CLM-02'],'issues':[]})
            if prompt.startswith('Direct an original'):
                return '# Test fixture treatment\nContext, synchronization, failure and consequence.'
            if prompt.startswith('Write a complete social-media storyboard'):
                return json.dumps({'title':'Email connection fixture','scenes':scenes})
            if prompt.startswith('Review this storyboard'):
                return json.dumps({'passed':True,'issues':[]})
            raise AssertionError('Unexpected model call in pipeline fixture')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            original_database=settings.database_url
            settings.database_url='sqlite:///'+str(root/'studio.db')
            try:
                init_db()
                with patch.multiple('backend.services.project_service',PROJECTS_DIR=str(root/'projects'),OUTPUT_DIR=str(root/'output')), \
                     patch.object(ai_service,'check_ready'),patch.object(ai_service,'generate',side_effect=generate), \
                     patch.object(research_service,'fetch_page_article',return_value=(text1+' '+text2+' ')*2), \
                     patch.dict(os.environ, {'CSRGO_RENDER_TEST':'1'}):
                    service=ProjectService()
                    project=service.create_project({'topic':'Email synchronization','target_duration':10,'draft_render':True,
                        'render_engine':'remotion','source_urls':['https://example.com/fixture']})
                    service._run_pipeline(project['id'],'controlled-test-job')
                    completed=service.get_project(project['id'])
                    self.assertEqual(completed['status'],'completed',completed.get('error_message'))
                    self.assertTrue((root/'output'/f"{project['slug']}.mp4").is_file())
                    qc=json.loads((root/'projects'/project['slug']/'renders/qc.json').read_text())
                    self.assertTrue(qc['passed'],qc)
                    self.assertTrue(qc['checks']['narration_audible_in_export'])
            finally:
                settings.database_url=original_database

    def test_native_remotion_export(self):
        self.render_fixture('remotion')

    def test_native_hyperframes_export(self):
        self.render_fixture('hyperframes')
