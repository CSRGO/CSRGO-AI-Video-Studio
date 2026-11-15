"""Real CPU media integration; model responses are explicit test fixtures, not live AI."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from backend.services.tts_service import tts_service
from backend.services.audio_service import audio_service
from backend.services.render_service import render_service
from backend.services.visual_service import visual_service
from backend.services.quality_service import quality_service
from backend.services.subtitle_service import subtitle_service


class MediaIntegrationTests(unittest.TestCase):
    def test_real_voice_sfx_music_animation_mux_and_quality_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ['audio', 'visuals/components', 'renders', 'final', 'research', 'subtitles']:
                (root / name).mkdir(parents=True, exist_ok=True)
            scenes = [
                {'scene_number': 1, 'title': 'Email synchronization',
                 'narration': 'Outlook connects to an email server to synchronize your inbox and messages.',
                 'visual_subject': 'email inbox', 'emotion': 'curious', 'pause_after': .2,
                 'sound_events': [{'progress': .4, 'cue': 'click', 'action': 'open mail'}]},
                {'scene_number': 2, 'title': 'Connection interrupted',
                 'narration': 'If that connection fails, new mail cannot synchronize until access is restored.',
                 'visual_subject': 'mail connection failure', 'emotion': 'concerned', 'pause_after': .2,
                 'sound_events': [{'progress': .5, 'cue': 'error_alert', 'action': 'connection alert'}]},
            ]
            timing = tts_service.synthesize_scenes(scenes, str(root / 'audio'), target_duration=10)
            self.assertLess(timing[-1]['end_time'], 10)
            subtitle_service.generate_srt(timing, str(root / 'subtitles/captions.srt'))
            for idx in (1, 2):
                # Deliberately hand-authored test fixtures to verify renderer behavior without an LLM.
                code = '''function renderDynamicScene_INDEX(ctx,p,W,H){
ctx.fillStyle='#18336B';ctx.fillRect(0,0,W,H);
ctx.strokeStyle='#dfefff';ctx.lineWidth=3;ctx.strokeRect(W*.08,H*.2,W*.84,H*.5);
ctx.fillStyle='#dfefff';ctx.font='bold '+(W*.055)+'px monospace';ctx.fillText('Outlook · TEST FIXTURE',W*.12,H*.27);
for(let i=0;i<4;i++){ctx.strokeRect(W*.12,H*(.32+i*.075),W*.35,H*.045);}
ctx.fillStyle=INDEX===1?'#8ddeef':'#fda0a0';ctx.fillRect(W*(.55+p*.18),H*.4,W*.12,H*.12);
ctx.fillStyle='#dfefff';ctx.font=(W*.04)+'px monospace';ctx.fillText(INDEX===1?'SYNCHRONIZING':'CONNECTION LOST',W*.12,H*.65);
}'''.replace('INDEX', str(idx))
                path = root / 'visuals/components' / f'scene_{idx:02d}.js'
                path.write_text(code)
                Path(str(path) + '.json').write_text(json.dumps({'engine': 'Claude Code', 'style_slug': 'blueprint', 'test_fixture': True}))
            story = {'title': 'Media integration fixture', 'total_target_duration': 10, 'scenes': scenes}
            html = str(root / 'visuals/index.html')
            visual_service.generate_html_scene(story, timing, 'blueprint', '9:16', html)
            visual = render_service.inspect_scenes(html, str(root / 'renders/frames'), width=360, height=640)
            (root / 'renders/visual_check.json').write_text(json.dumps(visual))
            metadata = [{**scene, 'start': timing[i]['start_time'],
                         'end': timing[i+1]['start_time'] if i+1 < len(timing) else 10}
                        for i, scene in enumerate(scenes)]
            production = audio_service.build_multi_stem_production(10, str(root), 'media-fixture', timing, metadata, topic='Email connection')
            self.assertAlmostEqual(production['cues']['sfx_events'][1]['timestamp'],
                                   timing[1]['start_time'] + .5 * (10 - timing[1]['start_time']), places=2)
            raw = str(root / 'renders/raw.mp4')
            final = str(root / 'final/video.mp4')
            render_service.render_video_frames(html, raw, width=360, height=640)
            render_service.mux_video_audio(raw, production['mix_path'], final)
            quality_service.generate_contact_sheet(final, str(root / 'renders/contact_sheet.jpg'))
            source = {'source_id': 'SRC-01', 'extracted_text': 'Outlook is an email application.'}
            claim = {'claim_text': source['extracted_text'], 'supporting_source_ids': ['SRC-01'],
                     'evidence': [{'source_id': 'SRC-01', 'quote': source['extracted_text']}]}
            (root / 'research/sources.json').write_text(json.dumps([source]))
            (root / 'research/claims.json').write_text(json.dumps([claim]))
            qc = quality_service.run_qc_suite(final, 10, storyboard=story, project_dir=str(root), expected_dimensions=(360,640))
            self.assertTrue(qc['passed'], qc)
            self.assertTrue(qc['checks']['narration_audible_in_export'])
            # Reject an export that has the same video but silent audio.
            silent = str(root / 'final/silent.mp4')
            render_service._ffmpeg(['-i', final, '-af', 'volume=0', '-c:v', 'copy', silent])
            self.assertFalse(quality_service.verify_exported_narration(silent, str(root / 'audio')))
            # An otherwise valid video must also fail the requested-duration gate.
            qc = quality_service.run_qc_suite(final, 30)
            self.assertFalse(qc['checks']['duration_valid'])


if __name__ == '__main__':
    unittest.main()
