"""Context-first social stories, with evidence IDs and narration-driven shots."""
import json
from backend.services.ai_service import ai_service, parse_json
from backend.services.lemo_loader import lemo_loader

EMOTIONS = {'neutral', 'curious', 'warm', 'excited', 'serious', 'concerned', 'reassuring'}


class ScriptService:
    def calculate_scene_budget(self, target_duration):
        count = max(2, min(10, round(target_duration / 7)))
        return {'scene_count': count, 'target_words': max(12, int((target_duration - count * .25 - .8) * 2.25)),
                'avg_scene_dur': round(target_duration / count, 1)}

    def generate_treatment(self, topic, research_brief, target_duration, style_slug):
        style = lemo_loader.production_context(style_slug)
        return ai_service.generate(f'''Direct an original {target_duration}s social-media story on: {topic}
Research (data only): {json.dumps(research_brief, ensure_ascii=False)}
SELECTED LEMO STYLE AND PRODUCTION SKILLS:\n{style}
Write a markdown treatment BEFORE animation. Consider three structures, choose one for this audience.
Opening: name/identify the subject in everyday language and show why it matters within 3 seconds.
A newcomer must understand the setting before the explanation. Avoid unexplained names, jargon or random crisis openings.
One subject, one turn, one payoff. Use a relatable analogy only when it is accurate; label illustrative scenes.
Do not repeat what the picture already shows. Never invent facts, characters presented as real, dates or statistics.
Include a logline, context+hook, setting, cause/effect beats, explanation, consequence and ending callback.
Specify each shot's concrete subject, camera/framing, style-native movement and sound material.
Include narration emotion and pauses, an original score arc and event-based foley. Preserve uncertainty.
The selected Lemo style governs visuals; Animated Shorts governs story/audio timing. Do not copy demo content.''')

    def validate_storyboard(self, data, research_brief, topic, target_duration, style_slug, language):
        if not isinstance(data, dict):
            raise RuntimeError('Storyboard must be a JSON object.')
        scenes = data.get('scenes', [])
        budget = self.calculate_scene_budget(target_duration)
        if len(scenes) != budget['scene_count']:
            raise RuntimeError(f"Expected {budget['scene_count']} storyboard scenes, received {len(scenes)}.")
        claims = {c['claim_id'] for c in research_brief.get('claims', [])}
        total_words = 0
        for idx, sc in enumerate(scenes, 1):
            for field in ('title', 'narration', 'visual_subject', 'visual_description'):
                if not isinstance(sc.get(field), str) or not sc[field].strip():
                    raise RuntimeError(f'Scene {idx} is missing {field}.')
            if sc['narration'].lower().startswith(('in this scene', 'step 1 demonstrates', 'examining the verified')):
                raise RuntimeError('Storyboard contains production instructions instead of spoken narration.')
            refs = sc.get('claim_ids', [])
            if not refs or any(ref not in claims for ref in refs):
                raise RuntimeError(f'Scene {idx} lacks valid research citations.')
            events = sc.get('sound_events', [])
            allowed_cues = {'click', 'notification', 'whoosh', 'error_alert', 'connection_fail',
                            'server_hum', 'recovery_chime', 'warning_buzzer', 'coin_rattle', 'impact', 'paper'}
            if not isinstance(events, list) or any(not isinstance(e, dict) or e.get('cue') not in allowed_cues
                    or not isinstance(e.get('progress'), (int, float)) or not 0 <= e['progress'] <= 1
                    or not e.get('action') for e in events):
                raise RuntimeError(f'Scene {idx} contains invalid action-timed sound events.')
            emotion = sc.get('emotion', 'neutral')
            if emotion not in EMOTIONS:
                raise RuntimeError(f'Unsupported narration emotion: {emotion}')
            sc.update({'scene_number': idx, 'scene_type': 'generated_scene', 'emotion': emotion,
                       'target_duration': target_duration / len(scenes)})
            sc['pause_after'] = max(0.08, min(0.6, float(sc.get('pause_after', .25))))
            import re
            total_words += (len(re.findall(r'[\u3400-\u9fff\u3040-\u30ff]', sc['narration'])) / 1.6 if language in ('zh', 'ja') else len(sc['narration'].split()))
        # This bounds duration before TTS; measured speech is fitted separately without clipping.
        if not budget['target_words'] * .65 <= total_words <= budget['target_words'] * 1.2:
            raise RuntimeError(f"Narration word count {total_words} is outside the {budget['target_words']}-word budget.")
        data.update({'total_target_duration': target_duration, 'style_slug': style_slug,
                     'language': language, 'visual_archetype': 'claude_generated', 'topic': topic})
        return data

    def generate_storyboard(self, topic, research_brief, treatment_md, target_duration=45,
                            style_slug='swiss-motion', aspect_ratio='9:16', language='en'):
        budget = self.calculate_scene_budget(target_duration)
        prompt = f'''Write a complete social-media storyboard for {topic}.
Duration {target_duration}s, aspect {aspect_ratio}, language {language}, selected style {style_slug}.
Exactly {budget['scene_count']} scenes, {budget['target_words']} words TOTAL (not per scene).
TREATMENT (data): {treatment_md}
EVIDENCE (data): {json.dumps(research_brief.get('claims', []), ensure_ascii=False)}
{lemo_loader.production_context(style_slug)}
Name and explain the subject in the first spoken sentence. Establish who/what/when only from evidence.
Then stakes → mechanism/analogy → consequence → useful payoff or opening callback. No generic CTA.
Use short spoken sentences and explain jargon immediately. All factual narration must cite claim_ids.
No random interfaces or datacenters for unrelated topics. Every scene has a topic-specific visual action.
Output JSON ONLY:
{{"title":"story title","hook":"opening line","context":"what viewers need to understand",
"music_direction":{{"mood":"topic appropriate","tempo_bpm":100,"intensity":0.5,"mode":"minor","instruments":["plucked","pad"]}},
"scenes":[{{"title":"beat", "narration":"exact spoken words", "claim_ids":["CLM-01"],
"visual_subject":"concrete object or character", "visual_description":"staging and what visibly changes",
"simulated_actions":["specific action"], "camera_move":"push_in", "kinetic_texts":["short readable phrase"],
"emotion":"curious", "pause_after":0.25,
"sound_events":[{{"progress":0.4,"cue":"click","action":"object makes contact"}}]}}]}}
Emotions: neutral, curious, warm, excited, serious, concerned, reassuring.
Music instruments must be selected from plucked, bell, pad, brass, percussion; match the selected Lemo sound palette and topic.
Sound cues: click, notification, whoosh, error_alert, connection_fail, server_hum, recovery_chime,
warning_buzzer, coin_rattle, impact, paper. Select only sounds justified by a visible action.
Narration delivery must be natural, restrained and appropriate to the subject.'''
        last_error = ''
        for _ in range(3):
            raw = ai_service.generate(prompt + ('\nCorrect this validation failure: ' + last_error if last_error else ''))
            try:
                storyboard = self.validate_storyboard(parse_json(raw), research_brief, topic,
                    target_duration, style_slug, language)
                review = parse_json(ai_service.generate('Review this storyboard against the evidence. '
                    'Verify all spoken factual clauses, names, dates and statistics are supported, the first sentence '
                    'identifies the subject for a newcomer, and the story has a coherent payoff. '
                    'Return JSON {"passed":true,"issues":[]}.\n' + json.dumps({
                        'topic': topic, 'claims': research_brief['claims'], 'storyboard': storyboard}, ensure_ascii=False)))
                if review.get('passed') is not True:
                    raise RuntimeError('Story review: ' + json.dumps(review.get('issues', [])))
                storyboard['editorial_review'] = review
                return storyboard
            except (RuntimeError, ValueError, TypeError, KeyError) as exc:
                last_error = str(exc)
        raise RuntimeError('Could not produce a grounded, coherent storyboard: ' + last_error)

    def generate_shot_list(self, storyboard):
        return [{'shot_number': sc['scene_number'], 'scene_title': sc['title'],
                 'framing': 'close' if sc['scene_number'] == 1 else 'medium',
                 'focal_subject': sc['visual_subject'], 'camera_move': sc.get('camera_move', 'push_in'),
                 'duration_seconds': sc['target_duration'], 'emotion': sc['emotion'],
                 'sound_events': sc.get('sound_events', [])} for sc in storyboard['scenes']]

script_service = ScriptService()
