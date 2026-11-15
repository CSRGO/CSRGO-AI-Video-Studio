"""Render the actual Claude components; never dispatch to unrelated stock scenes."""
import html
import json
import re
from pathlib import Path


class VisualService:
    def get_dimensions(self, aspect_ratio, draft=False):
        dimensions = {'9:16': (1080, 1920), '16:9': (1920, 1080), '1:1': (1080, 1080), '4:5': (1080, 1350)}
        if aspect_ratio not in dimensions:
            raise ValueError('Unsupported aspect ratio')
        w, h = dimensions[aspect_ratio]
        return (w // 2, h // 2) if draft else (w, h)

    def generate_html_scene(self, storyboard, narration_timing, style_slug, aspect_ratio,
                            output_html_path, subtitles_enabled=True):
        path = Path(output_html_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        w, h = self.get_dimensions(aspect_ratio)
        scenes = storyboard['scenes']
        if not scenes or len(narration_timing) != len(scenes):
            raise RuntimeError('Every scene requires a narration timing entry.')
        duration = storyboard.get('total_target_duration') or narration_timing[-1]['end_time'] + .8
        code, timeline = [], []
        for idx, (sc, timing) in enumerate(zip(scenes, narration_timing), 1):
            component = path.parent / 'components' / f'scene_{idx:02d}.js'
            manifest = json.loads(Path(str(component) + '.json').read_text(encoding='utf-8'))
            if manifest['style_slug'] != style_slug or manifest['engine'] != 'Claude Code':
                raise RuntimeError('Scene component does not match the selected style or generation engine.')
            code.append(component.read_text(encoding='utf-8'))
            timeline.append({**sc, 'index': idx, 'start': timing['start_time'], 'speech_end': timing['end_time'],
                             'end': narration_timing[idx]['start_time'] if idx < len(scenes) else duration})
        # JSON and generated code cannot terminate the HTML script element.
        safe_json = json.dumps(timeline, ensure_ascii=False).replace('<', '\\u003c')
        components = re.sub(r'</script', lambda m: '<' + r'\/script', '\n'.join(code), flags=re.I)
        document = '''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>__TITLE__</title><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#10131a}
canvas{width:100vw;height:100vh;display:block}#caption{position:fixed;left:8%;right:8%;bottom:12%;
text-align:center;font:600 clamp(16px,3.3vw,42px)/1.35 system-ui;color:white;pointer-events:none}
#caption span{background:rgba(10,15,24,.86);padding:.15em .35em;box-decoration-break:clone;border-radius:.2em}
</style></head><body><canvas id="stage" width="__W__" height="__H__"></canvas><div id="caption"></div>
<script>
const scenes=__SCENES__, W=__W__, H=__H__, canvas=document.getElementById('stage'), ctx=canvas.getContext('2d');
window.DUR=__DURATION__; window.SCENES=scenes; window.RENDER_ERRORS=[];
__COMPONENTS__
window.render=function(t){
 t=Math.max(0,Math.min(window.DUR-.000001,t));
 const sc=scenes.find(s=>t>=s.start&&t<s.end)||scenes[0];
 const p=Math.max(0,Math.min(1,(t-sc.start)/(sc.end-sc.start)));
 ctx.reset(); ctx.clearRect(0,0,W,H); ctx.save();
 const fn=window['renderDynamicScene_'+sc.index];
 if(typeof fn!=='function')throw new Error('Missing Claude component '+sc.index);
 fn(ctx,p,W,H); ctx.restore();
 const caption=document.getElementById('caption');caption.replaceChildren();
 if(__CAPTIONS__&&t<=sc.speech_end){
  const words=sc.narration.split(/\\s+/);const chunks=[];
  for(let i=0;i<words.length;i+=7)chunks.push(words.slice(i,i+7).join(' '));
  const c=Math.min(chunks.length-1,Math.floor((t-sc.start)/Math.max(.01,sc.speech_end-sc.start)*chunks.length));
  const span=document.createElement('span');span.textContent=chunks[c]||'';caption.appendChild(span);
 }
};
window.addEventListener('error',e=>window.RENDER_ERRORS.push(e.message));
window.render(0);window.READY=true;
</script></body></html>'''
        replacements = {'__TITLE__': html.escape(storyboard.get('title', 'Video')),
                        '__W__': str(w), '__H__': str(h), '__SCENES__': safe_json,
                        '__DURATION__': str(duration), '__CAPTIONS__': json.dumps(subtitles_enabled),
                        '__COMPONENTS__': components}
        for key, value in replacements.items():
            document = document.replace(key, value)
        path.write_text(document, encoding='utf-8')
        return str(path)

visual_service = VisualService()
