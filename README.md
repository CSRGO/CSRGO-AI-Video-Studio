# CSRGO AI Video Studio

> **100% Free, Local-First AI Video Production Studio for Windows**  
> Produce research-backed, cinematic vertical videos (YouTube Shorts, Instagram Reels, TikToks) entirely on your local machine using local Ollama models, offline Kokoro speech, multi-stem procedural audio synthesis, live internet research, and dual production toolkits (**Lemo-Opuscar** & **Claude Animated Shorts**).

---

## 1. System Overview & Architecture

CSRGO AI Video Studio is engineered specifically for Windows workstations with moderate hardware constraints (Intel Core i5 9th Gen, NVIDIA GeForce GTX 1650 4GB VRAM, 16GB RAM). It eliminates cloud APIs, subscriptions, and massive diffusion models in favor of deterministic code-driven visual simulation, event-anchored fact-gathering, and local neural models.

```
USER TOPIC / GITHUB REPO
    │
    ▼
1. Event-Anchored Research Engine (backend/services/research_service.py)
    │  ├─► Establishes unique event_id (e.g. MSFT-EXO-20261112)
    │  ├─► Isolates temporal window & filters out historical incident markers
    │  └─► Emits research.json, sources.json, claims.json, and research_report.md
    │
    ▼
2. Lemo-Opuscar Creative Director (backend/services/script_service.py)
    │  ├─► DIRECTOR.md treatment-first workflow (TREATMENT.md) with 3-second hook
    │  ├─► Multi-scene storyboard compiler (storyboard.json) with scene-specific types
    │  └─► Shot List compiler (SHOT_LIST.json) with camera paths, framing & lighting
    │
    ▼
3. Production & Synthesis
    │  ├─► Offline Kokoro ONNX Voice (24kHz WAV per line with boundary timestamps)
    │  ├─► Synchronized Subtitles (.srt + burned-in frosted bottom pill)
    │  ├─► Multi-Stem Procedural Audio (backend/services/audio_service.py)
    │  │   ├── stem_voice.wav (Speech track)
    │  │   ├── stem_music.wav (Original score seeded by project hash + ducked -14dB)
    │  │   ├── stem_sfx.wav (Event-based SFX: UI, alerts, server hums, recovery chimes)
    │  │   ├── mix.wav (Master composite mastered to -14 LUFS)
    │  │   └── audio_cues.json, music_plan.json, cues.md, mix.py
    │  └─► Visual Simulation Worlds (backend/services/visual_service.py)
    │      ├── Outlook Mailbox Failure Scene (Realistic client, frozen loader, alert)
    │      ├── M365 Service Health Cascade Scene (Exchange/OWA degradation, Downdetector spike)
    │      ├── Incident Scope & Timeline Scene (Chronological sequence & region nodes)
    │      ├── Infrastructure Bottleneck Scene (NOC cluster rack view, reconnect overload)
    │      ├── Service Recovery Flow Scene (Traffic rerouting, staged node reboots)
    │      ├── Cloud Resilience Takeaway Scene (Multi-tenancy dependency lessons)
    │      └── Git / Agent / Neural Network Simulation Engines
    │
    ▼
4. Playwright Chromium (Deterministic Frame Capture @ 24 FPS with per-shot camera keys)
    │
    ▼
5. FFmpeg Mastering (libx264 8.8x Real-Time CPU encoding + -14 LUFS Loudnorm)
    │
    ▼
6. Strict Quality Assurance Suite (backend/services/quality_service.py)
    │  ├─► Visual uniqueness & contact sheet tile variance check (rejects identical shots)
    │  ├─► Multi-track audio stem presence & duration match verification
    │  ├─► Factual claim source verification
    │  └─► 6-frame visual contact sheet (contact_sheet.jpg) + FFprobe metadata (qc.json)
    │
    ▼
FINAL H.264 MP4 VIDEO (Saved in /output and project workspace)
```

---

## 2. Hardware & Environment Specifications

- **Operating System**: Windows 10 / 11 64-bit
- **CPU**: Intel Core i5 (9th Generation or equivalent)
- **GPU**: NVIDIA GeForce GTX 1650 (4GB VRAM) — *Protected against VRAM exhaustion*
- **RAM**: 16GB
- **Python**: 3.11.9 (in `.venv`)
- **Node.js**: 20+ (running Node 26)
- **Encoder**: FFmpeg 9.0.2 & FFprobe
- **Local LLMs**:
  - `qwen3:1.7b` for scriptwriting & storyboard planning
  - `qwen2.5-coder:3b` for Claude Code animation programming & code generation
- **Claude Code Engine**: Local CLI subprocess execution (`claude`) connected via Anthropic-compatible Ollama bridge (`http://127.0.0.1:11434`) with zero cloud dependencies.

---

## 3. Permanent Local Claude Code & Ollama Architecture

The studio operates with **zero manual configuration**: opening the application and clicking **Generate Video** automatically orchestrates the entire workflow locally.

```
USER INTERACTION: Click "Generate Video"
    │
    ▼
[backend/services/ollama_manager.py]
    ├─► 1. Checks if Ollama is running (auto-launches `ollama serve` if offline)
    ├─► 2. Verifies local models exist (qwen3:1.7b and qwen2.5-coder:3b)
    ├─► 3. Verifies model inference readiness
    ├─► 4. Verifies Claude Code CLI installation (`claude`)
    └─► 5. Configures Anthropic-compatible environment:
           ANTHROPIC_BASE_URL = "http://127.0.0.1:11434"
           ANTHROPIC_AUTH_TOKEN = "ollama"
           ANTHROPIC_API_KEY    = "ollama"
           ENABLE_CLAUDEAI_MCP_SERVERS = "false"
    │
    ▼
[backend/services/lemo_loader.py]
    ├─► Indexes 100 creative styles from `vendor/lemo-opuscar/styles/`
    └─► Generates compact, token-conscious Director's Rule Cards for local LLMs
    │
    ▼
[backend/services/claude_animation_worker.py]
    ├─► Programmatically invokes `claude` CLI non-interactively (`-p`)
    ├─► Passes scene objectives, duration, and selected Lemo style rules
    ├─► Generates real, topic-specific Canvas / Remotion animation code
    ├─► Automatically validates JavaScript syntax via Node.js
    ├─► Triggers multi-turn auto-repair (up to 3 attempts) if syntax errors occur
    └─► Saves component code to `projects/<slug>/visuals/components/scene_NN.js`
    │
    ▼
[backend/services/visual_service.py]
    ├─► Embeds Claude Code components into deterministic Playwright Canvas
    └─► Applies camera movements, dynamic subtitles, and character host
    │
    ▼
[backend/services/audio_service.py & render_service.py]
    ├─► Composes multi-stem audio (voice, procedural music, event SFX)
    ├─► Playwright frame capture @ 24 FPS + FFmpeg H.264 encode
    └─► Masters audio to -14 LUFS and muxes final production MP4
```

### Persistent Configuration: `config/local_ai.yaml`

The studio persists all AI engine settings in `config/local_ai.yaml`:

```yaml
ai:
  provider: ollama
  endpoint: http://127.0.0.1:11434
  local_only: true
  planning_model: qwen3:1.7b
  coding_model: qwen2.5-coder:3b

claude_code:
  enabled: true
  mandatory: true
  execution_mode: subprocess
  auto_initialize: true
  auto_repair: true
  max_repair_attempts: 3
  timeout_seconds: 45
  executable: claude

production:
  use_selected_lemo_skill: true
  dynamic_scene_generation: true
  narration_driven_timeline: true
  scene_specific_audio: true
  visual_quality_checks: true
```

---

## 4. Comprehensive Test Suite (Tests A through F)

All core requirements are verified via the automated test suite runner:

```cmd
.\.venv\Scripts\python.exe test_claude_ollama_suite.py
```

### Verification Results

| Test ID | Test Category | Target Objective | Execution Result |
| :--- | :--- | :--- | :--- |
| **Test A** | **Local Inference** | Claude Code executes against local Ollama `qwen2.5-coder:3b` with 0 external network requests | **✓ PASSED** (2.16s) |
| **Test B** | **Animation Generation** | Claude Code generates real canvas animation code; validated via Node.js syntax checker; rendered via Playwright to PNG | **✓ PASSED** (17.53s, 613 bytes code, 13.7 KB frame) |
| **Test C** | **Lemo Style Distinction** | `swiss-motion` (warm cream paper `#EAE9E5`) vs `blueprint` (deep Prussian blue `#18336B`) verified through RGB pixel distribution | **✓ PASSED** (7.58s, Distinct color spaces verified) |
| **Test E** | **Restart Persistence** | Engine auto-initializes on startup using `config/local_ai.yaml` with zero manual environment variables | **✓ PASSED** (0.41s) |
| **Test F** | **Failure Handling** | Offline port (11439) accurately detected; reports controlled error; auto-recovers on active endpoint | **✓ PASSED** (2.32s) |
| **Test D** | **Complete Video Production** | Full 10-stage automated pipeline: research, script, TTS, subtitles, Claude Code components, Playwright 24fps render, multi-stem audio, -14 LUFS mastering | **✓ PASSED** (`cache-stampede-resilience-1ffe81.mp4`, 8.75 MB, 39.0s) |

---

## 5. Quick Start (Windows)

### Prerequisites
Before running the setup, ensure the following tools are installed on your workstation:
1. **Python 3.11+**: [python.org](https://www.python.org/downloads/) (ensure "Add Python to PATH" is checked)
2. **Node.js 20+**: [nodejs.org](https://nodejs.org/)
3. **FFmpeg & FFprobe**: [ffmpeg.org](https://ffmpeg.org/) (ensure `ffmpeg` and `ffprobe` are accessible from your terminal PATH)
4. **Ollama**: [ollama.com](https://ollama.com/)
   - Pull the required local models:
     ```cmd
     ollama pull qwen3:1.7b
     ollama pull qwen2.5-coder:3b
     ```

### 1. Clone the Repository
```cmd
git clone https://github.com/CSRGO/CSRGO-AI-Video-Studio.git
cd CSRGO-AI-Video-Studio
```

### 2. One-Click Environment Setup
Run from Windows Command Prompt:
```cmd
setup_windows.bat
```
Or from Git Bash:
```bash
./setup_gitbash.sh
```
This automated setup script:
- Creates the Python virtual environment (`.venv`)
- Initializes `.env` from `.env.example`
- Installs all backend production dependencies
- Installs the Playwright Chromium headless browser
- Automatically downloads Kokoro ONNX offline voice weights into `vendor/lemo-opuscar/core/tts/`
- Installs frontend React/Vite packages
- Executes the 12-point system verification suite

### 3. System & Hardware Verification
Run comprehensive diagnostics verifying all subsystems at any time:
```cmd
.\.venv\Scripts\python.exe verify_installation.py
.\.venv\Scripts\python.exe diagnostics.py
```

### 4. Starting the Studio
Double-click or run from command prompt:
```cmd
start_windows.bat
```
This script automatically:
1. Verifies local Ollama service connectivity (launches `ollama serve` if offline).
2. Starts the FastAPI backend at `http://127.0.0.1:8000`.
3. Starts the Vite React dashboard at `http://127.0.0.1:5173`.
4. Opens your default web browser to the studio dashboard.

### 5. Accessing the Studio
- **Studio Dashboard**: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- **REST API & Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Exported Videos**: `./output/`

### 6. Safe Shutdown
Double-click or run:
```cmd
stop_windows.bat
```
This safely frees ports 8000 and 5173.

---

## 6. Acceptance Tests & Verified Results

### Acceptance Test: November 12–13, 2026 Microsoft Outlook Outage
```cmd
.\.venv\Scripts\python.exe run_msft_outage_test.py
```
- **Topic**: The November 12–13, 2026 Microsoft Outlook / Exchange Online outage: automated health check failures, traffic bottlenecks, and service restoration.
- **Duration**: 63.8s (6 distinct scenes x 10s), 1080x1920 vertical, 24 fps, voice: `af_bella`.
- **Status**: **PASSED (100% of checks passed)**.
- **Exported Video**: [output/november-2026-microsoft-outlook-outage-b7d2ca.mp4](file:///C:/Users/csr85/CSRGO-AI-Video-Studio/output/november-2026-microsoft-outlook-outage-b7d2ca.mp4) (14.79 MB).
- **Contact Sheet**: `projects/november-2026-microsoft-outlook-outage-b7d2ca/renders/contact_sheet.jpg`.

### Technical Topic Acceptance Tests
```cmd
.\.venv\Scripts\python.exe test_suite_runner.py A   # Git Internals (Commit DAG, SHA-1 Box, Terminal)
.\.venv\Scripts\python.exe test_suite_runner.py B   # AI Agent Tool Use (Reasoning graph, Browser DOM inspector)
.\.venv\Scripts\python.exe test_suite_runner.py C   # Neural Networks (Multi-layer propagation & backpropagation waves)
```

| Test | Subject | Visual Archetype | Duration | Status | QC Checks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Microsoft Outage** | Nov 2026 Outlook Incident | `microsoft_outage_investigation` | 63.8s | **PASSED** | 10/10 Passed (Diversity, Stems, Claims, FFprobe) |
| **Test A** | Git Internals | `git_repository_simulation` | 22.7s | **PASSED** | 8/8 Passed (Playable, 1080x1920, 24fps) |
| **Test B** | AI Agent Tool Use | `ai_agent_workbench` | 43.4s | **PASSED** | 8/8 Passed (Playable, 1080x1920, 24fps) |
| **Test C** | Neural Networks | `neural_network_layers` | 36.5s | **PASSED** | 8/8 Passed (Playable, 1080x1920, 24fps) |

---

## 7. Visual Storytelling Engines (No Repeated Visual Subjects)

Rather than presenting generic text cards, every scene renders a distinct visual environment tailored to the narrative:

### Microsoft Outlook Outage (6 Distinct Visual Scenes):
1. **Scene 1 (`outlook_inbox_failure`)**: Authentic Microsoft Outlook interface with folder tree (`Inbox`, `Drafts`, `Sent Items`), mail message list, rotating circular loader that stutters and freezes, and yellow/red connection warning banner (`"DISCONNECTED: Attempting to connect to Exchange Online..."`) with pulsing retry button.
2. **Scene 2 (`m365_service_impact`)**: Microsoft 365 Service Health Dashboard with degraded service cards, red status pills on Exchange Online and Outlook Web Access, and an interactive Downdetector global report spike (>120,000 reports).
3. **Scene 3 (`incident_scope_timeline`)**: High-tech chronological incident timeline with event markers (Nov 12 18:00 UTC start, Nov 12 20:30 UTC peak, Nov 13 04:00 UTC mitigation, Nov 14 02:00 UTC restoration) alongside geographic impact nodes.
4. **Scene 4 (`infrastructure_bottleneck`)**: Cloud NOC server rack cluster showing automated orchestrator health checks pulling 45% of server nodes offline, funnelling client reconnect queues into surviving nodes and triggering CPU/RAM overload (>98%).
5. **Scene 5 (`service_recovery_flow`)**: Step-by-step traffic rerouting diagram redirecting requests to alternate healthy datacenters while server nodes cycle back online to 100% operational.
6. **Scene 6 (`cloud_resilience_takeaway`)**: Multi-region resilience architecture diagram illustrating decoupling health check thresholds, circuit breakers, and cloud dependency takeaways.

---

## 8. Multi-Stem Audio Engine

The procedural audio engine composes an original musical score seeded by the project hash, progressing through distinct emotional movements:
- **`stem_voice.wav`**: Dry, normalized 24kHz narration from Kokoro ONNX offline voice.
- **`stem_music.wav`**: Original procedural score in project-unique key and tempo, dynamically ducked by -14 dB during dialogue.
- **`stem_sfx.wav`**: Event-based synchronized sound effects (UI notifications, connection fail buzzes, error alerts, datacenter hums, recovery chimes).
- **`mix.wav`**: Master composite mastered to broadcast standard -14 LUFS / -1.2 dBTP.
- **`audio_cues.json` & `cues.md`**: Master timeline cue sheet mapping all events and movements.
- **`mix.py`**: Standalone executable Python recipe recreating the stem mix.

---

## 9. Directory Structure

```
CSRGO-AI-Video-Studio/
├── backend/
│   ├── api/routes.py                   # REST endpoints (/projects, /research, /sources, /claims, /audio...)
│   ├── core/config.py                  # Pydantic Settings
│   ├── database/db.py                  # Native SQLite database manager
│   ├── services/
│   │   ├── audio_service.py            # Multi-stem procedural score & event SFX generator
│   │   ├── brand_service.py            # Brand vector SVG registry & Microsoft/Outlook assets
│   │   ├── github_service.py           # GitHub repo cloner & Coder model inspector
│   │   ├── health_service.py           # Hardware monitoring
│   │   ├── ollama_service.py           # Ollama client wrapper
│   │   ├── project_service.py          # Master orchestrator & sequential production pipeline
│   │   ├── quality_service.py          # Strict QC suite (visual variance, stems, claims)
│   │   ├── render_service.py           # Playwright frame renderer & FFmpeg muxer
│   │   ├── research_service.py         # Event-anchored DuckDuckGo & httpx research engine
│   │   ├── script_service.py           # Storyboard planner, director treatment & word budgeter
│   │   ├── style_service.py            # 99 Lemo-Opuscar style catalog
│   │   ├── subtitle_service.py         # SRT generator
│   │   └── tts_service.py              # Kokoro ONNX offline voice manager & auto-downloader
│   └── main.py                         # FastAPI application entrypoint
├── frontend/
│   ├── src/
│   │   ├── App.jsx                     # 10-page studio dashboard with 4-tab project inspector
│   │   ├── main.jsx                    # React entrypoint
│   │   └── styles.css                  # Dark studio stylesheet
│   └── vite.config.js                  # Vite configuration
├── vendor/
│   ├── lemo-opuscar/                   # Creative style repertoire & production tools
│   └── claude-animated-shorts/         # 3D world, character & audio DSP reference toolkit
├── projects/                           # Self-contained project workspaces
├── output/                             # Exported final MP4 videos
├── .env.example                        # Template environment variables
├── ENGINE_AUDIT.md                     # Comprehensive production engine audit report
├── verify_installation.py              # 12-point system verification script
├── diagnostics.py                      # Diagnostic verification script
├── run_msft_outage_test.py             # Acceptance test runner for November 2026 Microsoft Outage
├── run_network_marketing_production.py # Acceptance test runner for Network Marketing production
├── test_claude_ollama_suite.py         # Comprehensive local Claude Code & Ollama test suite
├── test_dual_styles.py                 # Multi-style distinct visual validation test
├── test_suite_runner.py                # Acceptance test runner for technical topics
├── setup_windows.bat                   # Single-click setup script (CMD)
├── setup_gitbash.sh                    # Git Bash setup script
├── start_windows.bat                   # Single-click launcher
├── stop_windows.bat                    # Clean shutdown script
└── requirements.txt                    # Pinned Python dependencies
```

---

## 10. Attributions & Licences

- **Lemo-Opuscar**: Creative director architecture, style catalog, and render contract by Lemomo ([@lemomo_ai](https://x.com/lemomo_ai)), vendored under its respective open-source licence in `vendor/lemo-opuscar/`.
- **Claude Animated Shorts**: 3D world composition, character billboarding, and audio synthesis architecture by MromiDev ([claude-animated-shorts](https://github.com/mromidev/claude-animated-shorts)), vendored under MIT in `vendor/claude-animated-shorts/`.
- **Kokoro ONNX**: High quality open-source offline TTS model by Hexgrad, packaged via `kokoro-onnx`.
- **FFmpeg**: Licensed under LGPL/GPL.
- **FastAPI, React 19, Vite, Playwright**: Licensed under MIT/Apache 2.0.
