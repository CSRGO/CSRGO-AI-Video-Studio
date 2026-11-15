"""Use the upstream yt-script instructions and executable hook-scoring tool."""
import importlib.util
import json
from functools import lru_cache
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / 'vendor/youtube-agent-skill/skills/yt-script'


@lru_cache(maxsize=1)
def hook_tool():
    spec = importlib.util.spec_from_file_location('csrgo_youtube_hookscore', SKILL_ROOT / 'hookscore.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def story_context():
    skill = (SKILL_ROOT / 'SKILL.md').read_text(encoding='utf-8')
    # Keep production prompts focused; complete upstream instructions stay vendored.
    skill = skill.split('## The shape', 1)[1].split('## The gate', 1)[0]
    formulas = json.loads((SKILL_ROOT / 'hooks.json').read_text(encoding='utf-8'))
    shapes = [{'name': h['name'], 'shape': h['shape'], 'fails_when': h['fails_when']} for h in formulas['hooks']]
    return ('YOUTUBE YT-SCRIPT SKILL:\n' + skill + '\nFORMULA GUIDANCE (examples are not topic facts):\n' +
        json.dumps(shapes, ensure_ascii=False) + '\nAPPLICATION BRIEF: The audience is a first-time viewer. '
        'Use the configured narrator; no personal creator voice has been learned. Scale beats to the requested duration. '
        'Keep the subject clear in the opening, deliver the promised payoff, and never invent a number for a higher hook score. '
        'The user requested automatic generation, so return complete output without a conversational approval question. '
        'Nothing is uploaded to YouTube. Candidate hooks must cite the approved claim IDs.')


def analyze_hooks(storyboard, language='en'):
    selected = storyboard['scenes'][0]['narration']
    if language not in ('en', 'en-us', 'en-gb'):
        return {'selected_hook': selected, 'scored': False, 'reason': 'The upstream hook scorer is calibrated for English.'}
    tool = hook_tool()
    candidates = [selected]
    for item in storyboard.get('hook_options', [])[:5]:
        text = item.get('text') if isinstance(item, dict) else None
        if isinstance(text, str) and text.strip() and text.strip() not in candidates:
            candidates.append(text.strip())
    panels = []
    for text in candidates:
        parts, verdict, formula, hits = tool.score(text)
        panels.append({'hook': text, 'properties': parts, 'verdict': verdict, 'band': tool.band(verdict),
                       'formula': formula, 'selected_for_narration': text == selected})
    panels.sort(key=lambda panel: -panel['verdict'])
    return {'selected_hook': selected, 'scored': True, 'candidates': panels,
            'top_two': panels[:2], 'tool': 'youtube-agent-skill/yt-script/hookscore.py',
            'note': 'Scores are writing heuristics, not predictions of views. Only the reviewed narration is spoken.'}
