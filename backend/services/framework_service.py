"""Real Remotion and Hyperframes adapters; no substitution when an engine fails."""
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from backend.services.visual_service import visual_service

ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / 'renderer'


class FrameworkService:
    def check_ready(self, engine):
        if engine == 'canvas':
            return
        if engine not in ('remotion', 'hyperframes'):
            raise ValueError('Unsupported renderer')
        if not shutil.which('node') or not (RENDERER / 'node_modules' / ('remotion' if engine == 'remotion' else 'hyperframes')).exists():
            raise RuntimeError('Renderer dependencies are missing. Run npm ci in the renderer directory (Node 22+).')
        version = subprocess.run(['node', '--version'], capture_output=True, text=True, timeout=5)
        if version.returncode or int(version.stdout.strip().lstrip('v').split('.')[0]) < 22:
            raise RuntimeError('Remotion/Hyperframes integration requires Node.js 22 or later.')

    def skill_context(self, engine):
        self.check_ready(engine)
        if engine == 'remotion':
            files = [RENDERER / 'skills/remotion' / name for name in ('SKILL.md', 'markup.md', 'timing.md')]
        elif engine == 'hyperframes':
            base = RENDERER / 'node_modules/hyperframes/dist/skills/hyperframes'
            files = [base / 'SKILL.md', base / 'references/runtimes.md']
        else:
            return ''
        return '\n\n'.join(p.read_text(encoding='utf-8') for p in files)

    def prepare(self, engine, storyboard, timing, style_slug, aspect_ratio, project_dir, fps=24, draft=False, captions=True):
        self.check_ready(engine)
        width, height = visual_service.get_dimensions(aspect_ratio, draft=draft)
        folder = Path(project_dir) / 'visuals' / engine
        folder.mkdir(parents=True, exist_ok=True)
        duration = float(storyboard['total_target_duration'])
        scenes = [{**scene, 'start': t['start_time'], 'speech_end': t['end_time'],
                   'end': timing[i+1]['start_time'] if i+1 < len(timing) else duration}
                  for i, (scene, t) in enumerate(zip(storyboard['scenes'], timing))]
        manifest = {'engine': engine, 'width': width, 'height': height, 'fps': fps,
                    'duration': duration, 'scenes': scenes, 'project_dir': str(Path(project_dir).resolve())}
        if engine == 'remotion':
            for i in range(1, len(scenes) + 1):
                component = Path(project_dir) / 'visuals/components' / f'scene_{i:02d}.jsx.json'
                provenance = json.loads(component.read_text(encoding='utf-8'))
                if provenance.get('engine') != 'Claude Code' or provenance.get('style_slug') != style_slug:
                    raise RuntimeError('React scene provenance does not match the selected style and Claude Code engine.')
            imports = '\n'.join(f'import Scene{i} from {json.dumps(str((Path(project_dir)/"visuals/components"/f"scene_{i:02d}.jsx").resolve()))};'
                                for i in range(1, len(scenes)+1))
            data = json.dumps(scenes, ensure_ascii=False)
            source = f'''import React from 'react';
import {{registerRoot,Composition,AbsoluteFill,Sequence,useCurrentFrame,useVideoConfig}} from 'remotion';
{imports}
const scenes={data};const components=[{','.join(f'Scene{i}' for i in range(1,len(scenes)+1))}];
function Shot({{scene,Component,frames}}){{
 const frame=useCurrentFrame();const {{width,height,fps}}=useVideoConfig();
 const progress=Math.min(1,frame/Math.max(1,frames-1));
 const speechFrames=(scene.speech_end-scene.start)*fps;
 const words=scene.narration.split(/\\s+/);const chunks=[];
 for(let i=0;i<words.length;i+=7)chunks.push(words.slice(i,i+7).join(' '));
 const caption=chunks[Math.min(chunks.length-1,Math.floor(frame/Math.max(1,speechFrames)*chunks.length))];
 return <AbsoluteFill><Component progress={{progress}} width={{width}} height={{height}} scene={{scene}}/>
 {"<div style={{position:'absolute',left:'8%',right:'8%',bottom:'12%',textAlign:'center',fontFamily:'sans-serif',fontSize:width*.033,color:'white'}}>{frame<speechFrames&&<span style={{background:'#10131add',padding:'0.2em .35em',borderRadius:6}}>{caption}</span>}</div>" if captions else ''}
 </AbsoluteFill>;
}}
function Film(){{return <AbsoluteFill>{{scenes.map((scene,i)=>{{
 const start=Math.round(scene.start*{fps}),end=Math.round(scene.end*{fps});
 return <Sequence key={{i}} name={{scene.title}} from={{start}} durationInFrames={{Math.max(1,end-start)}}>
 <Shot scene={{scene}} Component={{components[i]}} frames={{Math.max(1,end-start)}}/></Sequence>;
}})}}</AbsoluteFill>;}}
function Root(){{return <Composition id="CSRGO" component={{Film}} width={{{width}}} height={{{height}}} fps={{{fps}}} durationInFrames={{{round(duration*fps)}}}/>;}}
registerRoot(Root);
'''
            entry = folder / 'index.jsx'
            entry.write_text(source, encoding='utf-8')
            manifest['entry'] = str(entry.resolve())
        elif engine == 'hyperframes':
            # Hyperframes officially supports Canvas via the deterministic hf-seek protocol.
            original = Path(project_dir) / 'visuals/index.html'
            visual_service.generate_html_scene(storyboard, timing, style_slug, aspect_ratio, str(original), captions)
            document = original.read_text(encoding='utf-8')
            assets = folder / 'assets'
            assets.mkdir(exist_ok=True)
            shutil.copyfile(RENDERER / 'node_modules/gsap/dist/gsap.min.js', assets / 'gsap.min.js')
            document = document.replace('<body>', f'<body><div id="root" data-composition-id="main" data-start="0" data-duration="{duration}" data-width="{width}" data-height="{height}" data-fps="{fps}">')
            document = document.replace('<canvas id="stage"', f'<canvas class="clip" data-start="0" data-duration="{duration}" id="stage"')
            document = document.replace('<script>', '<script src="assets/gsap.min.js"></script><script>', 1)
            document = document.replace('</body>', f'''<audio id="master-audio" class="clip" data-start="0" data-duration="{duration}" src="assets/mix.wav"></audio>
<script>
window.__timelines=window.__timelines||{{}};
const clock={{t:0}};const timeline=gsap.timeline({{paused:true}});
timeline.to(clock,{{t:{duration},duration:{duration},ease:'none'}});
window.__timelines.main=timeline;
window.addEventListener('hf-seek',e=>window.render(e.detail.time));
</script></div></body>''')
            (folder / 'index.html').write_text(document, encoding='utf-8')
            manifest['entry'] = str((folder / 'index.html').resolve())
        path = folder / 'render-project.json'
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def _run(self, command, cwd, env, progress_cb=None, timeout=1800):
        output = []
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        timer = threading.Timer(timeout, process.kill)
        timer.start()
        try:
            for line in process.stdout:
                output.append(line)
                if sum(len(item) for item in output) > 4_000_000:
                    raise RuntimeError("Renderer diagnostic output exceeded 4 MB.")
                try:
                    event = json.loads(line)
                    if progress_cb and isinstance(event, dict) and 'progress' in event:
                        progress_cb(70 + int(event['progress'] * .16), f"Rendering {event['progress']}%")
                except ValueError:
                    pass
            process.wait()
            if process.returncode:
                raise RuntimeError('Renderer failed: ' + ''.join(output)[-3500:])
        finally:
            timer.cancel()
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
        return ''.join(output)

    def render(self, manifest_path, output_path, progress_cb=None):
        manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        env = os.environ.copy()
        env.update({'DO_NOT_TRACK': '1', 'HYPERFRAMES_NO_TELEMETRY': '1'})
        if manifest['engine'] == 'remotion':
            self._run(['node', str(RENDERER / 'render.mjs'), manifest_path, output_path], str(RENDERER), env, progress_cb)
        else:
            folder = Path(manifest['entry']).parent
            env.setdefault('HYPERFRAMES_CACHE_DIR', str(folder / '.hyperframes/cache'))
            env.setdefault('HYPERFRAMES_CONFIG_DIR', str(folder / '.hyperframes/config'))
            shutil.copyfile(Path(manifest['project_dir']) / 'audio/mix.wav', folder / 'assets/mix.wav')
            browser = env.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
            if browser:
                env.setdefault('HYPERFRAMES_BROWSER_PATH', browser)
            cli = str(RENDERER / 'node_modules/hyperframes/bin/hyperframes.mjs')
            check = self._run(['node', cli, 'check', '--json', '--no-cache', '--budget', '90s'], str(folder), env, timeout=120)
            (folder / 'hyperframes-check.json').write_text(check, encoding='utf-8')
            start = check.find('{')
            if start < 0:
                raise RuntimeError('Hyperframes returned no JSON check report.')
            report, _ = json.JSONDecoder().raw_decode(check[start:])
            (folder / 'hyperframes-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            if report.get('ok') is not True or report.get('browserSkipped') is not False or not report.get('layout', {}).get('samples'):
                raise RuntimeError('Hyperframes checks did not complete successfully; inspect hyperframes-check.json.')
            self._run(['node', cli, 'render', '--fps', str(manifest['fps']), '--workers', '2',
                       '--quality', 'looks', '--json', '--skill', 'hyperframes', '-o', output_path], str(folder), env, progress_cb)
        if not Path(output_path).is_file() or Path(output_path).stat().st_size == 0:
            raise RuntimeError('Renderer produced no video.')

framework_service = FrameworkService()
