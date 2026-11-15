# CSRGO AI Video Studio

Turn a topic into a researched social-media story with a context-first script, selected Lemo visual style, offline narration, original procedural music, action-timed sound effects, captions and MP4 export.

**Generation always runs through Claude Code.** Choose **Ollama** or your installed **[FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi)** as its model source in **Models & Settings**. Choose Remotion for native React/SVG scenes, Hyperframes for deterministic HTML/Canvas timelines, or the legacy Canvas renderer. The Animated Shorts narration/audio workflow informs all three. Selecting a framework does not automatically reproduce the full Three.js bridge template or supply image assets.

## Run locally

Prerequisites: Python 3.11+, Node 22+, FFmpeg/FFprobe, Claude Code (`claude --version`), and either Ollama or FreeLLMAPI. FFmpeg needs its `rubberband` filter for expressive pitch processing and duration fitting. Inference runs sequentially to avoid loading multiple local models on a 4 GB GPU.

Install on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m backend.services.tts_service
Copy-Item .env.example .env  # only if .env does not already exist
cd frontend
npm ci
npm run build
cd ..
npm ci --prefix renderer
```

On Linux/macOS, use `.venv/bin/python` instead. If a system Chromium is already installed, the renderer can use it; `CHROMIUM_EXECUTABLE` explicitly selects an executable. No GPU is required for rendering or Kokoro speech.

Start the backend from the repository root:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal, run `npm run dev` from `frontend`, then open the dashboard on port 5173. Use a single backend worker: production jobs run in that process. Restarted jobs become interrupted/failed rather than appearing to run indefinitely.

## Connect your FreeLLMAPI desktop

1. Run FreeLLMAPI on the **same PC as the studio backend**. Its desktop default is **`http://127.0.0.1:31415`**; its server default is port 3001.
2. In the studio, open **Models & Settings → FreeLLMAPI**. Enter the server root URL. A trailing `/v1` is normalized away for Claude Code.
3. Enter the **unified key** from FreeLLMAPI's Keys page in the password field. This key remains in backend process memory until restart. For persistent setup, set `FREELLMAPI_API_KEY` in the backend environment or your ignored `.env` file; never commit it.
4. Save, then **Load models from saved source**. Select model IDs provided by your installation, or use `auto`, `auto:smart`, or a named profile such as `auto:coding` if you created it. FreeLLMAPI manages provider credentials, model availability, quotas and routing.
5. Use **Save & test connection**. This performs a real generation through Claude Code, not just a port check.

FreeLLMAPI already implements Anthropic Messages. The studio sets `ANTHROPIC_BASE_URL` to its root and `ANTHROPIC_AUTH_TOKEN` to the unified key; it explicitly removes `ANTHROPIC_API_KEY` from the child process to avoid conflicting authentication. No OpenRouter account or separate conversion gateway is needed. Model settings are saved in ignored `.env.ai.local`; keys are excluded.

A cloud backend cannot reach a FreeLLMAPI desktop running on your PC through `127.0.0.1`. Run both locally, or configure a separately reachable authenticated server. Do not paste keys into chat.

## Connect Ollama

Start `ollama serve`, pull `qwen3:1.7b` and `qwen2.5-coder:3b` (or choose your installed models), and select Ollama in Models & Settings. Claude Code uses Ollama's native Anthropic-compatible endpoint. Choose separate planning and coding models; settings remain fixed throughout an active production.

## Produce a story

Enter a specific topic and, for a news event, its date. You can supply up to six trusted source URLs when search is restricted. Select duration (10–120 seconds through the API), aspect ratio, style, narrator and language. Then generate.

The renderer selector is available on Create Video and on draft/failed projects before retry. Existing projects keep their original Canvas renderer until you change it; new UI projects default to Remotion.

- **Remotion:** Claude Code writes native JSX components using the pinned Remotion skills and the selected Lemo style. A registered React composition sequences scenes on the measured narration timeline; the real `@remotion/bundler` and `@remotion/renderer` produce H.264 frames. Remotion uses its bundled browser by default. If you explicitly choose another browser, set `REMOTION_BROWSER_EXECUTABLE` to its executable. Remotion license configuration is described in its [license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md); an applicable key can be supplied as `REMOTION_PRIVATE_LICENSE_KEY`.
- **Hyperframes:** Claude-generated Canvas scenes run through Hyperframes' native `hf-seek` protocol and a paused GSAP timeline. The pinned package supplies its actual production skill. `hyperframes check` must complete runtime/layout sampling before the native CLI renders. This adapter uses its documented Canvas runtime; it does not yet generate separately editable DOM sub-compositions for every shot. Caches stay inside the project and are removed with it.
- **Canvas:** preserves compatibility with earlier projects. It uses the original deterministic Chromium capture path.

A selected-engine failure is reported; it does not silently substitute another renderer. Both native engines receive the same narration, music/SFX master, captions and post-export quality gates. Renderer dependencies are pinned in `renderer/package-lock.json`.

The pipeline:

1. Builds search queries directly from the topic/date, without requiring a model JSON query plan, then searches public pages, and retrieves readable articles. Each factual claim needs an exact quotation and source ID, followed by a model entailment review. Missing sources or invalid citations stop production. Source-backed claims are not an independent guarantee of truth.
2. Writes a treatment using Lemo's real `DIRECTOR.md`, the selected style's complete `STYLE.md`, and the Animated Shorts story/audio rules. The opening introduces the subject for a newcomer, then develops a clear cause/effect story with a payoff. No canned Outlook incident dates or unrelated default scenes are inserted.
3. Creates and reviews a word-budgeted storyboard. Every scene cites research claims, specifies concrete visual actions, delivery emotion and sound events.
4. Synthesizes Kokoro speech, measures its duration, and applies restrained pitch/pacing changes. Modest time fitting respects the selected duration; scripts too long or short fail instead of clipping narration. Kokoro offers limited prosody, not actor-level emotional control. Choose a voice compatible with the selected language.
5. Invokes Claude Code to generate each selected-style React or Canvas component for the chosen renderer. Generated components are mandatory; code failures never substitute stock visual cards. Styles requiring generated image assets are shown as unavailable until an asset workflow is added.
6. Inspects generated scenes for runtime errors, blank frames, measurable motion and identical output; composes music from the style/story sound direction; aligns SFX to visible action progress on the measured narration timeline.
7. Renders frames, muxes explicit video/audio streams, applies loudness processing, creates a contact sheet and runs quality checks. Completion requires correct dimensions/FPS/duration, source references, audio stems, animation checks and correlation of decoded export audio with the real narration stem. Failed QC cannot publish an export.

Caption chunks are timed to measured scene speech, not word-level forced alignment. Visual quality and factual nuance still need human review before posting. The app supports React/SVG and Canvas interpretations of Lemo styles; full Three.js worlds and image-dependent media still need additional scene/asset implementation.

## Recover a failed research step

The earlier strict model-JSON query planner has been removed: malformed or missing `queries` can no longer stop retrieval. Supplied source URLs bypass search without first calling the model. Ollama supplies model inference, not web access. Automatic research tries DuckDuckGo, then an independent Bing RSS search endpoint if the first provider fails or returns no results. Verification challenges, HTTP errors, proxy denials and timeouts are reported separately; ordinary articles containing the word “anomaly” are not treated as challenge pages.

If research still fails, open the project in **Production & Inspect → Research recovery**, paste trusted article URLs about the same incident/date, and click **Save sources & retry**. The existing project and selected model are preserved. Direct article URLs skip search engines but still require Internet access to read the articles. Provider diagnostics are saved in the project's `research/research_diagnostics.json` and shown in the recovery panel. Restricted environments must allow `html.duckduckgo.com`, `www.bing.com`, and the article hosts they need to read.

## Files and cleanup

Each project keeps research, treatment, storyboard, generated scene code, speech, audio stems, captions, test frames and final export under `projects/<slug>`. Successful exports are also copied to `output`.

**Delete video & all files** removes the project workspace, its exported files, database row and render-job records. It is available in Project History and Video Library, with no second confirmation. Active productions cannot be deleted. File errors are reported so cleanup can be retried; unrelated projects are preserved.

## Validation

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm run build
```

Tests exercise source evidence, failure handling, Claude-only generation, native FreeLLMAPI authentication/streaming using a controlled protocol server, model persistence, deletion and QC gating. A CPU media integration test uses **explicit hand-authored scene fixtures**, real Kokoro synthesis, music/SFX, Chromium and FFmpeg to validate a 10-second MP4, including silent-export rejection. These tests do not claim a live model generated a publishable film. Missing Claude Code skips its protocol test; missing media prerequisites fail the integration test.

For the actual Remotion and Hyperframes export tests, install renderer dependencies and set `CSRGO_TEST_NATIVE_RENDERERS=1` before running the suite. They export explicit two-second scene fixtures through each native engine and inspect decoded animation, dimensions, FPS, duration and Hyperframes check results. A further controlled-model test exercises the complete 10-second Remotion pipeline with real Kokoro narration, music/SFX, muxing and final QC. These checks are opt-in in a normal test run; they require a usable browser. The cloud validation used the installed Chromium with the user's explicit permission, while local Remotion defaults to its bundled browser.

The older root-level acceptance scripts target the previous hard-coded demo pipeline and are not the readiness suite for this implementation. Live topic-to-video quality must be tested with your actual model connection and readable Internet sources.

## References and licenses

- [Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar): vendored style library, direction and production instructions; retain its included license.
- [Claude Animated Shorts](https://github.com/mromidev/claude-animated-shorts): MIT story/audio workflow and DSP references. Private study frames are not redistributed as generated-video assets.
- [FreeLLMAPI Claude Code setup](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/clients/01-agent-clients.md): native endpoint, unified key and model catalog conventions.

- [Hyperframes](https://github.com/heygen-com/hyperframes): pinned native renderer and production skill, Apache-2.0.
- [Remotion](https://github.com/remotion-dev/remotion) and [official agent skills](https://github.com/remotion-dev/skills): pinned renderer, native composition API and frame-driven React guidance; see the upstream license and `renderer/skills/README.md` for provenance.
