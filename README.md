# CSRGO AI Video Studio

Turn a topic into a researched social-media story with a context-first script, selected Lemo visual style, offline narration, original procedural music, action-timed sound effects, captions and MP4 export.

**Generation always runs through Claude Code.** Choose **Ollama** or your installed **[FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi)** as its model source in **Models & Settings**. The renderer is deterministic Canvas/Chromium plus FFmpeg; the Animated Shorts story/audio workflow informs the pipeline. This does not implement the full Three.js/Remotion bridge template or guarantee that every Lemo medium can be reproduced with Canvas.

## Run locally

Prerequisites: Python 3.11+, Node 20+, FFmpeg/FFprobe, Claude Code (`claude --version`), and either Ollama or FreeLLMAPI. FFmpeg needs its `rubberband` filter for expressive pitch processing and duration fitting. Inference runs sequentially to avoid loading multiple local models on a 4 GB GPU.

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

The pipeline:

1. Plans topic-specific research, searches public pages, and retrieves readable articles. Each factual claim needs an exact quotation and source ID, followed by a model entailment review. Missing sources or invalid citations stop production. Source-backed claims are not an independent guarantee of truth.
2. Writes a treatment using Lemo's real `DIRECTOR.md`, the selected style's complete `STYLE.md`, and the Animated Shorts story/audio rules. The opening introduces the subject for a newcomer, then develops a clear cause/effect story with a payoff. No canned Outlook incident dates or unrelated default scenes are inserted.
3. Creates and reviews a word-budgeted storyboard. Every scene cites research claims, specifies concrete visual actions, delivery emotion and sound events.
4. Synthesizes Kokoro speech, measures its duration, and applies restrained pitch/pacing changes. Modest time fitting respects the selected duration; scripts too long or short fail instead of clipping narration. Kokoro offers limited prosody, not actor-level emotional control. Choose a voice compatible with the selected language.
5. Invokes Claude Code to generate each selected-style Canvas component. Generated components are mandatory; code failures never substitute stock visual cards. Styles requiring generated image assets are shown as unavailable until an asset workflow is added.
6. Inspects generated scenes for runtime errors, blank frames, measurable motion and identical output; composes music from the style/story sound direction; aligns SFX to visible action progress on the measured narration timeline.
7. Renders frames, muxes explicit video/audio streams, applies loudness processing, creates a contact sheet and runs quality checks. Completion requires correct dimensions/FPS/duration, source references, audio stems, animation checks and correlation of decoded export audio with the real narration stem. Failed QC cannot publish an export.

Caption chunks are timed to measured scene speech, not word-level forced alignment. Visual quality and factual nuance still need human review before posting. The app currently supports code-rendered Canvas interpretations of Lemo styles; full 3D and image-dependent media need additional render/asset engines.

## Recover a failed research step

Ollama supplies model inference, not web access. Automatic research tries DuckDuckGo, then an independent Bing RSS search endpoint if the first provider fails or returns no results. Verification challenges, HTTP errors, proxy denials and timeouts are reported separately; ordinary articles containing the word “anomaly” are not treated as challenge pages.

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

The older root-level acceptance scripts target the previous hard-coded demo pipeline and are not the readiness suite for this implementation. Live topic-to-video quality must be tested with your actual model connection and readable Internet sources.

## References and licenses

- [Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar): vendored style library, direction and production instructions; retain its included license.
- [Claude Animated Shorts](https://github.com/mromidev/claude-animated-shorts): MIT story/audio workflow and DSP references. Private study frames are not redistributed as generated-video assets.
- [FreeLLMAPI Claude Code setup](https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/clients/01-agent-clients.md): native endpoint, unified key and model catalog conventions.
