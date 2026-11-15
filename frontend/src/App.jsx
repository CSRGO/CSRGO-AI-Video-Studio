import React, { useEffect, useState, useRef } from 'react';
import ModelSettings from './ModelSettings';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [health, setHealth] = useState(null);
  const [styles, setStyles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [voices, setVoices] = useState([]);
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [styleSearch, setStyleSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Project details tabs
  const [projectDetailTab, setProjectDetailTab] = useState('video');
  const [projectResearch, setProjectResearch] = useState(null);
  const [projectTreatment, setProjectTreatment] = useState(null);
  const [projectStoryboard, setProjectStoryboard] = useState(null);

  // Create Video Form State
  const [formData, setFormData] = useState({
    topic: '',
    name: '',
    mode: 'topic',
    source_url: '',
    target_duration: 30,
    aspect_ratio: '9:16',
    resolution: '1080x1920',
    fps: 24,
    language: 'en',
    voice: 'af_bella',
    speaking_speed: 1.0,
    style_slug: 'swiss-motion',
    music_enabled: true,
    sfx_enabled: true,
    subtitles_enabled: true,
    draft_render: false, expressive_voice: true, render_engine: 'remotion'
  });

  const [notice, setNotice] = useState('');
  const [deleting, setDeleting] = useState(null);
  const [sourceText, setSourceText] = useState('');
  const [recoverySources, setRecoverySources] = useState('');
  const [researchDiagnostics, setResearchDiagnostics] = useState(null);
  const [recoveryEngine, setRecoveryEngine] = useState('canvas');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [copiedNotification, setCopiedNotification] = useState(false);

  useEffect(() => {
    fetchHealth();
    fetchStyles();
    fetchVoices();
    fetchProjects();

    const interval = setInterval(() => {
      fetchHealth();
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // Poll active job status when a project is running
  useEffect(() => {
    if (!activeProject || (activeProject.status !== 'processing' && activeProject.status !== 'queued')) {
      return;
    }

    const jobInterval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/projects/${activeProject.id}/status`);
        if (res.ok) {
          const statusData = await res.json();
          setActiveJob(statusData.job);
          setActiveProject(prev => ({
            ...prev,
            status: statusData.status,
            stage: statusData.stage,
            progress: statusData.progress,
            output_video_path: statusData.output_video_path,
            error_message: statusData.error_message
          }));

          if (statusData.status === 'completed' || statusData.status === 'failed') {
            fetchProjects();
            loadProjectDetails(activeProject.id);
          }
        }
      } catch (err) {
        console.error('Error polling job status:', err);
      }
    }, 1500);

    return () => clearInterval(jobInterval);
  }, [activeProject?.id, activeProject?.status]);

  // Load project details when viewing a specific project
  async function loadProjectDetails(projId) {
    try {
      const [resR, resT, resS, resInputs] = await Promise.all([
        fetch(`${API}/api/projects/${projId}/research`).catch(() => null),
        fetch(`${API}/api/projects/${projId}/treatment`).catch(() => null),
        fetch(`${API}/api/projects/${projId}/storyboard`).catch(() => null),
        fetch(`${API}/api/projects/${projId}/research-inputs`).catch(() => null)
      ]);

      if (resInputs?.ok) {
        const inputs = await resInputs.json();
        setRecoverySources((inputs.source_urls || []).join('\n'));
        setResearchDiagnostics(inputs.diagnostics);
        setRecoveryEngine(inputs.render_engine || 'canvas');
      } else { setRecoverySources(''); setResearchDiagnostics(null); }

      if (resR && resR.ok) setProjectResearch(await resR.json());
      else setProjectResearch(null);

      if (resT && resT.ok) setProjectTreatment(await resT.json());
      else setProjectTreatment(null);

      if (resS && resS.ok) setProjectStoryboard(await resS.json());
      else setProjectStoryboard(null);
    } catch (e) {
      console.warn('Error loading project details:', e);
    }
  }

  async function fetchHealth() {
    try {
      const res = await fetch(`${API}/api/health`);
      if (res.ok) {
        setHealth(await res.json());
      } else {
        setHealth({ status: 'offline' });
      }
    } catch {
      setHealth({ status: 'offline' });
    }
  }

  async function fetchStyles() {
    try {
      const res = await fetch(`${API}/api/styles`);
      if (res.ok) {
        const data = await res.json();
        setStyles(data.styles || []);
        setCategories(['All', ...(data.categories || [])]);
      }
    } catch (e) {
      console.error('Error fetching styles:', e);
    }
  }

  async function fetchVoices() {
    try {
      const res = await fetch(`${API}/api/voices`);
      if (res.ok) {
        const data = await res.json();
        setVoices(data.voices || []);
      }
    } catch (e) {
      console.error('Error fetching voices:', e);
    }
  }

  async function fetchProjects() {
    try {
      const res = await fetch(`${API}/api/projects`);
      if (res.ok) {
        setProjects(await res.json() || []);
      }
    } catch (e) {
      console.error('Error fetching projects:', e);
    }
  }

  async function handleCreateAndProduce(e) {
    if (e) e.preventDefault();
    if (!formData.topic.trim()) return;

    setCreating(true);
    setCreateError('');

    try {
      // 1. Create project
      const createRes = await fetch(`${API}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...formData, source_urls: sourceText.split(/\n/).map(s => s.trim()).filter(Boolean) })
      });

      if (!createRes.ok) {
        const errData = await createRes.json();
        throw new Error(errData.detail || 'Failed to create project');
      }

      const newProj = await createRes.json();
      setActiveProject(newProj);
      setRecoveryEngine(newProj.render_engine || 'canvas');

      // 2. Trigger research-driven production pipeline
      const produceRes = await fetch(`${API}/api/projects/${newProj.id}/produce`, {
        method: 'POST'
      });

      if (!produceRes.ok) {
        const failure = await produceRes.json();
        throw new Error(failure.detail || 'Failed to start video production');
      }

      const jobData = await produceRes.json();
      setActiveJob(jobData.job);
      setActiveProject(prev => ({ ...prev, status: 'processing', stage: 'research', progress: 5 }));

      setActiveTab('queue');
      fetchProjects();
    } catch (err) {
      setCreateError(err.message || 'Error creating video project');
    } finally {
      setCreating(false);
    }
  }

  async function retryProduction(saveSources = false) {
    setCreating(true); setNotice('');
    try {
      {
        const update = await fetch(`${API}/api/projects/${activeProject.id}/research-inputs`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ render_engine: recoveryEngine, ...(saveSources ? { source_urls: recoverySources.split(/\n/).map(s => s.trim()).filter(Boolean) } : {}) })
        });
        if (!update.ok) { const error = await update.json(); throw new Error(typeof error.detail === 'string' ? error.detail : 'Enter up to six valid HTTP(S) article URLs.'); }
      }
      const res = await fetch(`${API}/api/projects/${activeProject.id}/produce`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Could not start production');
      setActiveJob(data.job);
      setActiveProject(p => ({ ...p, status: 'processing', stage: 'starting', progress: 0, error_message: null }));
      fetchProjects();
    } catch (e) { setNotice(e.message); } finally { setCreating(false); }
  }

  async function handleDeleteProject(id) {
    setDeleting(id); setNotice('');
    document.querySelectorAll('video').forEach(video => { if (video.src.includes(`/projects/${id}/`)) { video.pause(); video.removeAttribute('src'); video.load(); } });
    try {
      const response = await fetch(`${API}/api/projects/${id}`, { method: 'DELETE' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Deletion failed');
      await fetchProjects();
      if (activeProject?.id === id) { setActiveProject(null); setActiveJob(null); }
      setNotice('Video and all related files deleted.');
    } catch (err) { setNotice('Could not delete video: ' + err.message); }
    finally { setDeleting(null); }
  }

  function copyText(txt) {
    navigator.clipboard.writeText(txt);
    setCopiedNotification(true);
    setTimeout(() => setCopiedNotification(false), 2500);
  }

  const filteredStyles = styles.filter(s => {
    const matchesCat = selectedCategory === 'All' || s.category.toLowerCase() === selectedCategory.toLowerCase();
    const q = styleSearch.toLowerCase();
    const matchesSearch = !q || s.name.toLowerCase().includes(q) || s.category.toLowerCase().includes(q) || s.slug.includes(q);
    return matchesCat && matchesSearch;
  });

  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand" onClick={() => setActiveTab('dashboard')} style={{ cursor: 'pointer' }}>
          <span className="brand-mark">C</span>
          <div>
            CSRGO<span>AI VIDEO STUDIO</span>
          </div>
        </div>

        <div className="nav-label">CINEMATIC STUDIO</div>
        <button
          className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          ◈ <span>Dashboard</span>
        </button>
        <button
          className={`nav-item ${activeTab === 'create' ? 'active' : ''}`}
          onClick={() => setActiveTab('create')}
        >
          ✦ <span>Create Video</span>
        </button>
        <button
          className={`nav-item ${activeTab === 'queue' ? 'active' : ''}`}
          onClick={() => setActiveTab('queue')}
        >
          ⏱ <span>Production & Inspect</span>
          {activeProject && activeProject.status === 'processing' && (
            <span className="badge-pulse">LIVE</span>
          )}
        </button>
        <button
          className={`nav-item ${activeTab === 'projects' ? 'active' : ''}`}
          onClick={() => { fetchProjects(); setActiveTab('projects'); }}
        >
          ▤ <span>Project History</span>
          <span className="badge-count">{projects.length}</span>
        </button>
        <button
          className={`nav-item ${activeTab === 'videos' ? 'active' : ''}`}
          onClick={() => { fetchProjects(); setActiveTab('videos'); }}
        >
          ▶ <span>Video Library</span>
        </button>

        <div className="nav-label">LEMO-OPUSCAR REPERTOIRE</div>
        <button
          className={`nav-item ${activeTab === 'styles' ? 'active' : ''}`}
          onClick={() => setActiveTab('styles')}
        >
          🎨 <span>{styles.length || 100} Visual Styles</span>
        </button>
        <button
          className={`nav-item ${activeTab === 'voices' ? 'active' : ''}`}
          onClick={() => setActiveTab('voices')}
        >
          🎙 <span>{voices.length} Offline Voices</span>
        </button>
        <button
          className={`nav-item ${activeTab === 'audio' ? 'active' : ''}`}
          onClick={() => setActiveTab('audio')}
        >
          🎵 <span>Procedural Audio</span>
        </button>

        <div className="nav-label">DIAGNOSTICS</div>
        <button
          className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          ⚙ <span>Models & Settings</span>
        </button>
        <button
          className={`nav-item ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          📋 <span>Diagnostics Log</span>
        </button>

        <div className="sidebar-bottom">
          <span className="local-dot"></span> RESEARCH-DRIVEN STUDIO
          <small>Local rendering · your choice of model</small>
        </div>
      </aside>

      {/* Main Studio Area */}
      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Studio /</span>{' '}
            {activeTab.charAt(0).toUpperCase() + activeTab.slice(1).replace('-', ' ')}
          </div>
          <div className="top-status">
            <span className="local-dot"></span> {health?.ai?.provider === 'freellmapi' ? 'FREELLMAPI' : 'OLLAMA'} · CLAUDE CODE
          </div>
        </header>

        {notice && <div className="studio-notice" role="status">{notice}<button className="text-button" onClick={() => setNotice('')}>Dismiss</button></div>}
        {health?.ai && !health.ai.ready && <div className="studio-notice warning"><span>{health.ai.last_error}</span><button className="text-button" onClick={() => setActiveTab('settings')}>Configure models</button></div>}
        {copiedNotification && (
          <div className="toast-notification">✓ Copied to clipboard!</div>
        )}

        {/* ============================================================== */}
        {/* PAGE 1: DASHBOARD */}
        {/* ============================================================== */}
        {activeTab === 'dashboard' && (
          <div>
            <section className="welcome">
              <div>
                <div className="eyebrow">RESEARCH-DRIVEN CINEMATIC VIDEO ENGINE</div>
                <h1>
                  Produce stories that <span>visually demonstrate</span> reality.
                </h1>
                <p>
                  Turn a topic into a clear story: gather sources, explain the context, and bring it to life
                  in your selected Lemo style, with narration, music and sound tied to the action.
                </p>
                <div style={{ marginTop: '24px', display: 'flex', gap: '14px' }}>
                  <button className="primary-button" onClick={() => setActiveTab('create')}>
                    ✦ Create New Video →
                  </button>
                  <button className="secondary-button" onClick={() => setActiveTab('styles')}>
                    Browse style library
                  </button>
                </div>
              </div>
              <div className="welcome-art">🌐</div>
            </section>

            {/* System Status Grid */}
            <section className="system-panel">
              <div className="section-heading">
                <div>
                  <h2>Production Engine Status</h2>
                  <p>Hardware verification and engine diagnostics</p>
                </div>
                <span className={health?.ai?.ready ? "live-label good" : "live-label pending"}>{health?.ai?.ready ? "● MODEL CONNECTED" : "● SETUP NEEDED"}</span>
              </div>

              <div className="status-grid">
                <div className="status-card">
                  <span>RESEARCH & LLM</span>
                  <strong className={health?.ai?.ready ? 'good' : 'pending'}>
                    {health?.ai?.ready ? 'Model connected' : 'Model setup needed'}
                  </strong>
                  <small>{health?.ai?.planning_model || 'Configure in Models & Settings'}</small>
                </div>

                <div className="status-card">
                  <span>OFFLINE NEURAL SPEECH</span>
                  <strong className={health?.tts?.status === 'available' ? 'good' : 'pending'}>
                    {voices.length} Offline Voices
                  </strong>
                  <small>Kokoro v1.0 ONNX · 24kHz Neural</small>
                </div>

                <div className="status-card">
                  <span>VISUAL SIMULATION & ENCODER</span>
                  <strong className={health?.ffmpeg?.status === 'available' ? 'good' : 'pending'}>
                    Playwright + FFmpeg
                  </strong>
                  <small>Deterministic frames · CPU encoding</small>
                </div>

                <div className="status-card">
                  <span>LEMO-OPUSCAR STYLES</span>
                  <strong className="good">{styles.length} Styles in Library</strong>
                  <small>Swiss, Neon, Blueprint, Keynote & more</small>
                </div>
              </div>
            </section>

            {/* Recent Productions */}
            <section style={{ marginTop: '35px' }}>
              <div className="section-heading">
                <div>
                  <h2>Recent Productions ({projects.length})</h2>
                  <p>Click any project to view its video, research report, treatment, or contact sheet</p>
                </div>
                <button className="text-button" onClick={() => setActiveTab('projects')}>
                  View all ({projects.length}) →
                </button>
              </div>

              {projects.length === 0 ? (
                <div className="empty-box">
                  <p>No video productions yet.</p>
                  <button className="primary-button" onClick={() => setActiveTab('create')}>
                    Create Your First Video
                  </button>
                </div>
              ) : (
                <div className="project-grid">
                  {projects.slice(0, 3).map(p => (
                    <div key={p.id} className="project-card">
                      <div className="project-card-header">
                        <span className="badge-tag">{p.style_slug}</span>
                        <span className={`status-pill ${p.status}`}>{p.status.toUpperCase()}</span>
                      </div>
                      <h3>{p.name}</h3>
                      <p className="project-topic">{p.topic}</p>
                      <div className="project-meta">
                        <span>⏱ {p.actual_duration || p.target_duration}s</span>
                        <span>📐 {p.aspect_ratio}</span>
                        <span>🎙 {p.voice}</span>
                      </div>
                      <div className="project-actions">
                        <button
                          className="secondary-button"
                          onClick={() => {
                            setActiveProject(p); setRecoveryEngine(p.render_engine || 'canvas'); setActiveJob(null);
                            loadProjectDetails(p.id);
                            setActiveTab('queue');
                          }}
                        >
                          Inspect & Play ▶
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 2: CREATE VIDEO */}
        {/* ============================================================== */}
        {activeTab === 'create' && (
          <div className="create-panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">STEP 01 / STORY SPECIFICATION</div>
                <h2>Create a Research-Driven Video</h2>
                <p>CSRGO will gather web sources, plan visual simulations, and render the complete film.</p>
              </div>
              <span className="step-count">01 / DIRECT</span>
            </div>

            {createError && <div className="generation-error">⚠ {createError}</div>}

            <form onSubmit={handleCreateAndProduce}>
              {/* Input Mode */}
              <div className="mode-tabs">
                <button
                  type="button"
                  className={formData.mode === 'topic' ? 'selected' : ''}
                  onClick={() => setFormData(prev => ({ ...prev, mode: 'topic' }))}
                >
                  ✦ Topic + Web Research
                </button>
                <button
                  type="button"
                  className={formData.mode === 'github' ? 'selected' : ''}
                  onClick={() => setFormData(prev => ({ ...prev, mode: 'github' }))}
                >
                  ⌘ GitHub Repository to Video
                </button>
              </div>

              {formData.mode === 'topic' ? (
                <label className="field-label">
                  WHAT IS THE TOPIC OF YOUR VIDEO?
                  <textarea
                    rows={3}
                    value={formData.topic}
                    onChange={e => setFormData(prev => ({ ...prev, topic: e.target.value }))}
                    placeholder="Examples:
• How Git works behind the scenes (commit DAG, trees, SHA hashes)
• How AI agents use tools to complete autonomous tasks
• How neural networks learn (forward propagation, loss, backpropagation)"
                    required
                  />
                  <small>The research engine will cross-check facts and verify technical claims before scripting.</small>
                </label>
              ) : (
                <div className="github-box">
                  <label className="field-label">
                    GITHUB REPOSITORY URL
                    <input
                      type="url"
                      value={formData.source_url}
                      onChange={e => setFormData(prev => ({ ...prev, source_url: e.target.value, topic: e.target.value }))}
                      placeholder="https://github.com/owner/repository"
                      required
                    />
                    <small>Claude Code will research the repository page and explain its purpose using source-backed claims.</small>
                  </label>
                </div>
              )}

              <label className="field-label" style={{ marginTop: 18 }}>Trusted source URLs (optional, one per line)
                <textarea rows={2} value={sourceText} onChange={e => setSourceText(e.target.value)} placeholder="https://…" />
                <small>For a specific event, include its date in the topic. Source URLs help when web search is unavailable.</small>
              </label>
              <div className="model-summary"><span>Claude Code · {health?.ai?.provider === 'freellmapi' ? 'FreeLLMAPI' : 'Ollama'} · {health?.ai?.planning_model}</span>
                <button type="button" className="text-button" onClick={() => setActiveTab('settings')}>Change models →</button>
              </div>
              {/* Title */}
              <label className="field-label" style={{ marginTop: '18px' }}>
                PROJECT TITLE (OPTIONAL)
                <input
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Auto-generated if left blank"
                />
              </label>

              {/* Duration & Aspect Ratio */}
              <div className="form-grid-2" style={{ marginTop: '20px' }}>
                <label className="field-label">
                  VIDEO DURATION
                  <select
                    value={formData.target_duration}
                    onChange={e => setFormData(prev => ({ ...prev, target_duration: Number(e.target.value) }))}
                  >
                    <option value={10}>10 Seconds (Brief story)</option>
                    <option value={15}>15 Seconds (Quick short)</option>
                    <option value={30}>30 Seconds (Social reel)</option>
                    <option value={45}>45 Seconds (Explainer)</option>
                    <option value={60}>60 Seconds (Full story)</option>
                  </select>
                </label>

                <label className="field-label">
                  ASPECT RATIO & COMPOSITION
                  <select
                    value={formData.aspect_ratio}
                    onChange={e => setFormData(prev => ({
                      ...prev,
                      aspect_ratio: e.target.value,
                      resolution: e.target.value === '16:9' ? '1920x1080' : e.target.value === '1:1' ? '1080x1080' : e.target.value === '4:5' ? '1080x1350' : '1080x1920'
                    }))}
                  >
                    <option value="9:16">9:16 — YouTube Shorts / Reels / TikTok (1080x1920)</option>
                    <option value="16:9">16:9 — YouTube Landscape / Desktop (1920x1080)</option>
                    <option value="1:1">1:1 — Square Feed (1080x1080)</option>
                    <option value="4:5">4:5 — Instagram Portrait (1080x1350)</option>
                  </select>
                </label>
              </div>

              <label className="field-label" style={{ marginTop: 20 }}>Video renderer
                <select aria-label="Video renderer" value={formData.render_engine} onChange={e => setFormData(p => ({ ...p, render_engine: e.target.value }))}>
                  <option value="remotion">Remotion — React/SVG scenes and frame-based motion</option>
                  <option value="hyperframes">Hyperframes — HTML/Canvas timeline and native checks</option>
                  <option value="canvas">Canvas — legacy Chromium renderer</option>
                </select>
                <small>The selected Lemo style directs the visuals; the renderer controls how the code becomes video. Node 22+ and renderer dependencies are required.</small>
              </label>

              {/* Style Selector */}
              <div style={{ marginTop: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label className="field-label" style={{ margin: 0 }}>
                    VISUAL STYLE & SIMULATION GRAMMAR
                  </label>
                  <button type="button" className="text-button" onClick={() => setActiveTab('styles')}>
                    Browse style library →
                  </button>
                </div>
                <select
                  value={formData.style_slug}
                  onChange={e => setFormData(prev => ({ ...prev, style_slug: e.target.value }))}
                >
                  <optgroup label="Popular Visual Simulation Styles">
                    <option value="swiss-motion">Swiss Motion Graphics (Clean geometric grid, high contrast, typography)</option>
                    <option value="neon-tubes">Neon Tubes (Cyberpunk glowing wireframes, particle pulses, terminal lights)</option>
                    <option value="blueprint">Engineering Blueprint (Technical drafting lines, dimension markers, architecture)</option>
                    <option value="dark-keynote">Dark Tech Keynote (Matte obsidian cards, frosted glass, glowing orbs)</option>
                    <option value="circuit-board">Circuit Board (Microcontroller traces, data packet bus, binary streams)</option>
                    <option value="chalkboard">Chalkboard Explainer (Hand-drawn formulas, diagrams, mathematical sketches)</option>
                  </optgroup>
                  <optgroup label="All Styles in Library">
                    {styles.map(s => (
                      <option key={s.slug} value={s.slug} disabled={s.available === false}>
                        {s.name} ({s.category}){s.available === false ? ' · needs image assets' : ''}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </div>

              {/* Voice & Speed */}
              <div className="form-grid-2" style={{ marginTop: '20px' }}>
                <label className="field-label">
                  OFFLINE NARRATOR VOICE (KOKORO ONNX)
                  <select
                    value={formData.voice}
                    onChange={e => setFormData(prev => ({ ...prev, voice: e.target.value }))}
                  >
                    <optgroup label="Recommended Narrators">
                      <option value="af_bella">Bella (Female, American · Warm & Clear)</option>
                      <option value="am_michael">Michael (Male, American · Authoritative & Crisp)</option>
                      <option value="af_sarah">Sarah (Female, American · Professional)</option>
                      <option value="bm_george">George (Male, British · Technical Documentary)</option>
                    </optgroup>
                    <optgroup label="Other Voices">
                      {voices.map(v => (
                        <option key={v.id} value={v.id}>{v.name}</option>
                      ))}
                    </optgroup>
                  </select>
                </label>

                <label className="field-label">
                  SPEAKING SPEED ({formData.speaking_speed}x)
                  <input
                    type="range"
                    min="0.85"
                    max="1.2"
                    step="0.05"
                    value={formData.speaking_speed}
                    onChange={e => setFormData(prev => ({ ...prev, speaking_speed: parseFloat(e.target.value) }))}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#888' }}>
                    <span>0.85x (Deliberate)</span>
                    <span>1.0x (Optimal)</span>
                    <span>1.2x (Fast)</span>
                  </div>
                </label>
              </div>

              <div className="form-grid-2" style={{ marginTop: 20 }}>
                <label className="field-label">Narration language<select value={formData.language} onChange={e => { const language = e.target.value; const prefixes = { en: 'af_', hi: 'hf_', es: 'ef_', fr: 'ff_', ja: 'jf_', zh: 'zf_', pt: 'pf_', it: 'if_' }; const narrator = voices.find(v => v.id.startsWith(prefixes[language])); setFormData(p => ({ ...p, language, voice: narrator?.id || p.voice })); }}>
                  <option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option>
                  <option value="fr">French</option><option value="ja">Japanese</option><option value="zh">Chinese</option>
                  <option value="pt">Portuguese</option><option value="it">Italian</option>
                </select><small>Select a compatible narrator voice for your language.</small></label>
                <label className="checkbox-label"><input type="checkbox" checked={formData.expressive_voice} onChange={e => setFormData(p => ({ ...p, expressive_voice: e.target.checked }))} />
                  Topic-aware delivery (subtle pitch, pacing and pauses)
                </label>
              </div>
              {/* Audio & Rendering Switches */}
              <div className="switches-grid" style={{ marginTop: '24px' }}>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.music_enabled}
                    onChange={e => setFormData(prev => ({ ...prev, music_enabled: e.target.checked }))}
                  />
                  <span>Procedural Synthesizer Score (Ducked by 14dB during narration)</span>
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.sfx_enabled}
                    onChange={e => setFormData(prev => ({ ...prev, sfx_enabled: e.target.checked }))}
                  />
                  <span>Procedural Sound Effects (Whooshes, clicks, impacts, terminal typing)</span>
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.subtitles_enabled}
                    onChange={e => setFormData(prev => ({ ...prev, subtitles_enabled: e.target.checked }))}
                  />
                  <span>Synchronized Captions (.srt + glass subtitle pill)</span>
                </label>

                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.draft_render}
                    onChange={e => setFormData(prev => ({ ...prev, draft_render: e.target.checked }))}
                  />
                  <span>Draft Preview Quality (Half-resolution rendering)</span>
                </label>
              </div>

              {/* Action */}
              <div className="create-footer" style={{ marginTop: '32px' }}>
                <div style={{ fontSize: '12px', color: '#62708a' }}>
                  Web Research → Story Treatment → Visual Simulation → Muxing (-14 LUFS)
                </div>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={creating || !formData.topic.trim()}
                  style={{ padding: '14px 32px', fontSize: '14px' }}
                >
                  {creating ? 'Researching & Starting...' : '✦ Research & Produce Video →'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 3: PRODUCTION QUEUE & WORKBENCH INSPECTOR */}
        {/* ============================================================== */}
        {activeTab === 'queue' && (
          <div>
            <div className="section-heading">
              <div>
                <div className="eyebrow">PRODUCTION WORKBENCH</div>
                <h2>Video Pipeline & Artifact Inspector</h2>
                <p>Live progress, research report, story treatment, and quality verification</p>
              </div>
              {activeProject && (
                <span className={`status-pill ${activeProject.status}`}>
                  {activeProject.status.toUpperCase()}
                </span>
              )}
            </div>

            {!activeProject ? (
              <div className="empty-box">
                <p>No active production selected.</p>
                <button className="primary-button" onClick={() => setActiveTab('create')}>
                  Start a Video Production
                </button>
              </div>
            ) : (
              <div className="production-dashboard">
                {/* Live Progress Card */}
                <div className="pipeline-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <span className="badge-tag">{activeProject.style_slug}</span>
                      <h2 style={{ margin: '8px 0' }}>{activeProject.name}</h2>
                      <p style={{ color: '#62708a', fontSize: '13px' }}>{activeProject.topic}</p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div className="big-percent">{activeProject.progress || 0}%</div>
                      <small style={{ color: '#62708a' }}>{activeProject.stage}</small>
                    </div>
                  </div>

                  <div className="meter-bar">
                    <div
                      className="meter-fill"
                      style={{ width: `${Math.max(5, activeProject.progress || 0)}%` }}
                    ></div>
                  </div>

                  <div className="job-message">
                    <span className="local-dot"></span>
                    {activeJob?.message || activeProject.error_message || 'Processing workflow...'}
                  </div>

                  {['draft', 'failed'].includes(activeProject.status) && <label className="field-label" style={{ marginTop: 16 }}>Video renderer for this project
                    <select aria-label="Video renderer for this project" value={recoveryEngine} onChange={e => setRecoveryEngine(e.target.value)}>
                      <option value="remotion">Remotion (React scenes)</option><option value="hyperframes">Hyperframes (HTML/Canvas)</option><option value="canvas">Canvas (legacy)</option>
                    </select>
                  </label>}
                  {['draft', 'failed'].includes(activeProject.status) && <button className="primary-button" disabled={creating} onClick={() => retryProduction()} style={{ marginTop: 16 }}>
                    {creating ? 'Starting…' : activeProject.status === 'failed' ? 'Retry production' : 'Start production'}
                  </button>}

                  {activeProject.status === 'failed' && /research sources|research|article|search/i.test(activeProject.error_message || '') && <section className="research-recovery">
                    <h3>Research recovery</h3>
                    <p>Your model connection and web search are separate. Keep Ollama selected; search providers may require verification or be blocked by a firewall.</p>
                    <label className="field-label">Trusted article URLs (one per line, up to six)
                      <textarea rows={3} value={recoverySources} onChange={e => setRecoverySources(e.target.value)} placeholder="Paste links to reporting or official updates about the same incident and date." />
                    </label>
                    <button className="primary-button" style={{ marginTop: 12 }} disabled={creating || !recoverySources.trim()} onClick={() => retryProduction(true)}>
                      {creating ? 'Starting…' : 'Save sources & retry'}
                    </button>
                    {researchDiagnostics && <details style={{ marginTop: 14 }}><summary>Research diagnostics</summary>
                      {researchDiagnostics.reused_sources && <p>Reusing recently retrieved articles; citations and relevance are checked again.</p>}
                      {(researchDiagnostics.citation_attempts || []).map((a, i) => <p key={`citation-${i}`}>Citation check {a.attempt}: {a.accepted_total} accepted; {(a.rejected || []).length} needed repair.</p>)}
                      <ul>{(researchDiagnostics.search_attempts || []).map((a, i) => <li key={i}>{a.provider}: {a.reason || `${a.results} results`}</li>)}</ul>
                      {(researchDiagnostics.warnings || []).map((warning, i) => <p key={i}>{warning}</p>)}
                    </details>}
                  </section>}

                  {/* Visual Pipeline Stages */}
                  <div className="stages-flow">
                    {[
                      { key: 'research', label: 'Web Research' },
                      { key: 'treatment', label: 'Treatment' },
                      { key: 'script', label: 'Storyboard' },
                      { key: 'voice', label: 'Speech' },
                      { key: 'visuals', label: 'Simulation' },
                      { key: 'rendering', label: 'Render' },
                      { key: 'qc', label: 'QC Suite' },
                      { key: 'completed', label: 'Ready' }
                    ].map((st, idx) => {
                      const stages = ['created', 'starting', 'init_ai', 'research', 'treatment', 'script', 'voice', 'subtitles', 'claude_code', 'visuals', 'audio_mix', 'rendering', 'muxing', 'post_process', 'qc', 'completed'];
                      const currentIdx = stages.indexOf(activeProject.stage);
                      const stageIdx = stages.indexOf(st.key);
                      const isDone = currentIdx > stageIdx || activeProject.status === 'completed';
                      const isCurrent = activeProject.stage === st.key;

                      return (
                        <div key={st.key} className={`stage-step ${isDone ? 'done' : isCurrent ? 'current' : ''}`}>
                          <div className="step-circle">{isDone ? '✓' : idx + 1}</div>
                          <span>{st.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Sub-Tabs: Video Player | Research Report | Story Treatment | Storyboard */}
                <div style={{ marginTop: '30px' }}>
                  <div className="mode-tabs">
                    <button
                      className={projectDetailTab === 'video' ? 'selected' : ''}
                      onClick={() => setProjectDetailTab('video')}
                    >
                      ▶ Video & Quality
                    </button>
                    <button
                      className={projectDetailTab === 'research' ? 'selected' : ''}
                      onClick={() => {
                        setProjectDetailTab('research');
                        loadProjectDetails(activeProject.id);
                      }}
                    >
                      🔍 Research Sources ({projectResearch?.sources?.length || 0})
                    </button>
                    <button
                      className={projectDetailTab === 'treatment' ? 'selected' : ''}
                      onClick={() => {
                        setProjectDetailTab('treatment');
                        loadProjectDetails(activeProject.id);
                      }}
                    >
                      📝 Treatment & Shot List
                    </button>
                    <button
                      className={projectDetailTab === 'storyboard' ? 'selected' : ''}
                      onClick={() => {
                        setProjectDetailTab('storyboard');
                        loadProjectDetails(activeProject.id);
                      }}
                    >
                      🎬 Visual Scenes ({projectStoryboard?.scenes?.length || 0})
                    </button>
                  </div>

                  {/* TAB 1: VIDEO PLAYER */}
                  {projectDetailTab === 'video' && activeProject.status === 'completed' && (
                    <div className="video-player-card">
                      <div className="section-heading">
                        <div>
                          <div className="eyebrow" style={{ color: '#54d69a' }}>● READY TO PUBLISH</div>
                          <h2>{activeProject.name}</h2>
                          <p>Duration: {activeProject.actual_duration}s · Resolution: {activeProject.resolution}</p>
                        </div>
                        <div style={{ display: 'flex', gap: '10px' }}>
                          <a
                            href={`${API}/api/projects/${activeProject.id}/video`}
                            download
                            className="primary-button"
                          >
                            Download MP4 💾
                          </a>
                          <a
                            href={`${API}/api/projects/${activeProject.id}/srt`}
                            download
                            className="secondary-button"
                          >
                            Download Subtitles (.srt)
                          </a>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '32px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                        <div className="video-wrapper">
                          <video
                            controls
                            autoPlay
                            loop
                            playsInline
                            src={`${API}/api/projects/${activeProject.id}/video`}
                            style={{
                              maxWidth: '340px',
                              maxHeight: '600px',
                              borderRadius: '16px',
                              boxShadow: '0 16px 50px rgba(0,0,0,0.85)',
                              border: '1px solid #333'
                            }}
                          />
                        </div>

                        <div style={{ flex: 1, minWidth: '320px' }}>
                          <h3>Quality Control & Visual Diversity Verification</h3>
                          <div className="qc-box" style={{ marginTop: '12px' }}>
                            <div className="qc-item">✓ Duration: {activeProject.actual_duration}s (Measured via FFprobe)</div>
                            <div className="qc-item">✓ Visual Diversity: Dynamic visual simulation (No text-card slides)</div>
                            <div className="qc-item">✓ Audio Mastering: Two-pass loudnorm to -14 LUFS / True Peak -1.2 dBTP</div>
                            <div className="qc-item">✓ Subtitles: Clean frosted caption box with safe margins</div>
                          </div>

                          <h4 style={{ marginTop: '24px', marginBottom: '8px' }}>Frame Contact Sheet</h4>
                          <img
                            src={`${API}/api/projects/${activeProject.id}/contact-sheet`}
                            alt="Contact Sheet"
                            style={{ width: '100%', borderRadius: '10px', border: '1px solid #333' }}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {/* TAB 2: RESEARCH REPORT */}
                  {projectDetailTab === 'research' && (
                    <div className="create-panel">
                      <div className="section-heading">
                        <div>
                          <div className="eyebrow">VERIFIED WEB RESEARCH</div>
                          <h2>Internet Research Report</h2>
                          <p>Grounded in primary and authoritative web documentation</p>
                        </div>
                      </div>

                      {!projectResearch ? (
                        <p style={{ color: '#888' }}>Research brief is being compiled or not available.</p>
                      ) : (
                        <div>
                          <div className="qc-box" style={{ marginBottom: '24px' }}>
                            <strong>Summary:</strong>
                            <p style={{ marginTop: '6px', color: '#27364e' }}>{projectResearch.summary}</p>
                          </div>

                          <h3 style={{ marginBottom: '12px' }}>Discovered Primary Sources ({projectResearch.sources?.length || 0})</h3>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {projectResearch.sources?.map((src, i) => (
                              <div key={i} className="setting-row">
                                <div style={{ flex: 1 }}>
                                  <a
                                    href={src.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ color: '#5641b7', fontWeight: 600, textDecoration: 'none' }}
                                  >
                                    {src.title} ↗
                                  </a>
                                  <p style={{ fontSize: '12px', color: '#62708a', marginTop: '4px' }}>{src.snippet}</p>
                                </div>
                                <span className="badge-tag">{src.credibility}</span>
                              </div>
                            ))}
                          </div>

                          <h3 style={{ marginTop: '24px', marginBottom: '12px' }}>Key Factual Claims</h3>
                          <ul style={{ paddingLeft: '20px', color: '#52617b', fontSize: '13.5px', lineHeight: '1.8' }}>
                            {projectResearch.key_findings?.map((kf, i) => (
                              <li key={i}>{kf}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 3: TREATMENT & SHOT LIST */}
                  {projectDetailTab === 'treatment' && (
                    <div className="create-panel">
                      <div className="section-heading">
                        <div>
                          <div className="eyebrow">DIRECTOR.MD TREATMENT</div>
                          <h2>Creative Treatment & Camera Grammar</h2>
                          <p>Narrative arc, 3-second hook, and camera directions</p>
                        </div>
                      </div>

                      {!projectTreatment ? (
                        <p style={{ color: '#888' }}>Treatment is being generated...</p>
                      ) : (
                        <div>
                          <pre style={{
                            background: '#f4f6fb',
                            padding: '20px',
                            borderRadius: '10px',
                            whiteSpace: 'pre-wrap',
                            fontFamily: 'inherit',
                            fontSize: '13px',
                            lineHeight: '1.6',
                            color: '#27364e'
                          }}>
                            {projectTreatment.treatment}
                          </pre>

                          <h3 style={{ marginTop: '24px', marginBottom: '14px' }}>Shot List ({projectTreatment.shot_list?.length || 0} Shots)</h3>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
                            {projectTreatment.shot_list?.map((shot, i) => (
                              <div key={i} className="status-card">
                                <span style={{ color: '#6251d5' }}>SHOT {shot.shot_number} · {(shot.framing || 'medium').toUpperCase()}</span>
                                <strong>{shot.scene_title}</strong>
                                <small style={{ color: '#5641b7' }}>Camera Move: {shot.camera_move}</small>
                                <p style={{ fontSize: '11.5px', color: '#888', marginTop: '6px' }}>
                                  Subject: {shot.focal_subject}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 4: STORYBOARD SCENES */}
                  {projectDetailTab === 'storyboard' && (
                    <div className="create-panel">
                      <div className="section-heading">
                        <div>
                          <div className="eyebrow">VISUAL SCENE BREAKDOWN</div>
                          <h2>Interactive Simulation Plan</h2>
                          <p>Visual subjects, simulated UI actions, and spoken narration</p>
                        </div>
                      </div>

                      {!projectStoryboard ? (
                        <p style={{ color: '#888' }}>Storyboard is compiling...</p>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                          {projectStoryboard.hook_analysis && <section className="qc-box">
                            <h3>YouTube script hook review</h3>
                            <p>{projectStoryboard.hook_analysis.selected_hook}</p>
                            {projectStoryboard.hook_analysis.scored ? <>
                              <p>{projectStoryboard.hook_analysis.note}</p>
                              {(projectStoryboard.hook_analysis.top_two || []).map((hook, i) => <div key={i} style={{ marginTop: 12 }}>
                                <strong>{hook.verdict}/100 · {hook.formula}{hook.selected_for_narration ? ' · used in narration' : ' · alternative'}</strong>
                                <p>{hook.hook}</p>
                              </div>)}
                            </> : <p>{projectStoryboard.hook_analysis.reason}</p>}
                          </section>}
                          {projectStoryboard.scenes?.map((sc, i) => (
                            <div key={i} className="info-card">
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <h3>Scene 0{sc.scene_number} · {sc.title}</h3>
                                <span className="badge-tag">{sc.camera_move} · {sc.target_duration}s</span>
                              </div>
                              <p style={{ color: '#5641b7', fontWeight: 600, margin: '8px 0' }}>
                                🎬 Visual Subject: {sc.visual_subject}
                              </p>
                              <p style={{ color: '#27364e', fontSize: '13.5px' }}>
                                <strong>Narration:</strong> "{sc.narration}"
                              </p>
                              <p style={{ color: '#888a9e', fontSize: '12px', marginTop: '6px' }}>
                                <strong>Visual Description:</strong> {sc.visual_description}
                              </p>
                              <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
                                {sc.simulated_actions?.map((act, j) => (
                                  <span key={j} className="badge-count" style={{ fontSize: '10px' }}>
                                    ⚡ {act}
                                  </span>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 4: PROJECT HISTORY */}
        {/* ============================================================== */}
        {activeTab === 'projects' && (
          <div>
            <div className="section-heading">
              <div>
                <div className="eyebrow">PERSISTENT REPOSITORY</div>
                <h2>Project History ({projects.length})</h2>
                <p>Complete workspace retained locally with intermediate assets and research</p>
              </div>
              <button className="primary-button" onClick={() => setActiveTab('create')}>
                ✦ New Video Project
              </button>
            </div>

            <div className="project-grid">
              {projects.map(p => (
                <div key={p.id} className="project-card">
                  <div className="project-card-header">
                    <span className="badge-tag">{p.style_slug}</span>
                    <span className={`status-pill ${p.status}`}>{p.status.toUpperCase()}</span>
                  </div>
                  <h3>{p.name}</h3>
                  <p className="project-topic">{p.topic}</p>
                  <div className="project-meta">
                    <span>⏱ {p.actual_duration || p.target_duration}s</span>
                    <span>📐 {p.aspect_ratio}</span>
                    <span>🎙 {p.voice}</span>
                  </div>
                  <div className="project-actions">
                    <button
                      className="secondary-button"
                      onClick={() => {
                        setActiveProject(p); setRecoveryEngine(p.render_engine || 'canvas'); setActiveJob(null);
                        loadProjectDetails(p.id);
                        setActiveTab('queue');
                      }}
                    >
                      Inspect & Play
                    </button>
                    <button
                      className="delete-button"
                      disabled={deleting === p.id || p.status === 'processing'}
                      onClick={() => handleDeleteProject(p.id)}
                    >
                      {deleting === p.id ? 'Deleting…' : 'Delete video & all files'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 5: 99 VISUAL STYLES */}
        {/* ============================================================== */}
        {activeTab === 'styles' && (
          <div>
            <div className="section-heading">
              <div>
                <div className="eyebrow">LEMO-OPUSCAR REPERTOIRE</div>
                <h2>Lemo Visual Film Styles</h2>
                <p>Dynamic motion, camera grammar, and procedural rendering</p>
              </div>
              <input
                type="text"
                placeholder="Search styles..."
                value={styleSearch}
                onChange={e => setStyleSearch(e.target.value)}
                className="search-input"
              />
            </div>

            <div className="category-scroll">
              {categories.map(cat => (
                <button
                  key={cat}
                  className={`category-pill ${selectedCategory === cat ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="styles-gallery">
              {filteredStyles.map(s => (
                <div
                  key={s.slug}
                  className={`style-card ${formData.style_slug === s.slug ? 'selected' : ''}`}
                  onClick={() => {
                    if (s.available === false) { setNotice('This style requires generated image assets. Choose an available code-rendered style.'); return; }
                    setFormData(prev => ({ ...prev, style_slug: s.slug }));
                    setActiveTab('create');
                  }}
                >
                  <div className="style-card-image">
                    {s.has_poster ? (
                      <img src={`${API}/api/styles/${s.slug}/poster`} alt={s.name} loading="lazy" />
                    ) : (
                      <div className="placeholder-poster">🎨 {s.name}</div>
                    )}
                    <span className="style-num">#{s.num}</span>
                  </div>
                  <div className="style-card-body">
                    <h4>{s.name}</h4>
                    <span className="style-cat">{s.category}</span>
                    <p>{s.description}</p>
                    <button className="style-use-btn">
                      {s.available === false ? 'Image assets required' : formData.style_slug === s.slug ? '✓ Selected' : 'Use Style →'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 6: 54 OFFLINE VOICES */}
        {/* ============================================================== */}
        {activeTab === 'voices' && (
          <div>
            <div className="section-heading">
              <div>
                <div className="eyebrow">OFFLINE NEURAL VOICES</div>
                <h2>Kokoro Narrator Voices</h2>
                <p>High-fidelity 24kHz speech synthesized locally on CPU with zero internet</p>
              </div>
            </div>

            <div className="voices-grid">
              {voices.map(v => (
                <div key={v.id} className="voice-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>{v.name}</strong>
                    <span className="badge-tag">{v.accent}</span>
                  </div>
                  <small style={{ color: '#888' }}>ID: {v.id}</small>
                  <button
                    className="secondary-button"
                    style={{ marginTop: '12px', width: '100%' }}
                    onClick={() => {
                      setFormData(prev => ({ ...prev, voice: v.id }));
                      setActiveTab('create');
                    }}
                  >
                    Select this Voice
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 7: PROCEDURAL AUDIO */}
        {/* ============================================================== */}
        {activeTab === 'audio' && (
          <div>
            <div className="section-heading">
              <div>
                <div className="eyebrow">SOUND DESIGN</div>
                <h2>Procedural Audio & Foley Synthesis</h2>
                <p>Pure mathematical sound generation in NumPy/SciPy — zero samples needed</p>
              </div>
            </div>

            <div className="audio-cards-grid">
              <div className="info-card">
                <h3>Adaptive Procedural Score</h3>
                <p>
                  Generates multi-harmonic chords, ambient pads, sub-bass plucks, and high arpeggios
                  tailored to the millisecond duration of your video.
                </p>
                <div className="feature-list" style={{ marginTop: '14px' }}>
                  <div>✓ Master timeline beat-synchronization</div>
                  <div>✓ Automatic -14dB speech ducking with smooth ramps</div>
                  <div>✓ Master limiter & loudnorm -14 LUFS compliance</div>
                </div>
              </div>

              <div className="info-card">
                <h3>Synchronized Foley Sound Effects</h3>
                <p>Physics-modeled acoustic wave generation:</p>
                <div className="feature-list" style={{ marginTop: '14px' }}>
                  <div>✦ Whoosh / Transition (Swept bandpass noise filter)</div>
                  <div>✦ Click / Button Snap (Transient noise + high resonances)</div>
                  <div>✦ Keyboard Typing (Monospace terminal audio pulses)</div>
                  <div>✦ Thump / Impact (Damped low-frequency sine waves)</div>
                  <div>✦ Chime / Success (Overlapping harmonic decays)</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 8: VIDEO LIBRARY */}
        {/* ============================================================== */}
        {activeTab === 'videos' && (
          <div>
            <div className="section-heading">
              <div>
                <div className="eyebrow">PUBLISH-READY MEDIA</div>
                <h2>Exported Video Library</h2>
                <p>Direct MP4 and SRT downloads ready for social media publishing</p>
              </div>
            </div>

            <div className="project-grid">
              {projects.filter(p => p.status === 'completed').map(p => (
                <div key={p.id} className="project-card video-card">
                  <video
                    controls
                    preload="metadata"
                    src={`${API}/api/projects/${p.id}/video`}
                    style={{ width: '100%', maxHeight: '340px', borderRadius: '10px', background: '#000' }}
                  />
                  <div style={{ marginTop: '12px' }}>
                    <h4>{p.name}</h4>
                    <p style={{ fontSize: '12px', color: '#888' }}>{p.topic}</p>
                    <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                      <a
                        href={`${API}/api/projects/${p.id}/video`}
                        download
                        className="primary-button"
                        style={{ textDecoration: 'none', textAlign: 'center', flex: 1 }}
                      >
                        Download MP4
                      </a>
                      <a
                        href={`${API}/api/projects/${p.id}/srt`}
                        download
                        className="secondary-button"
                        style={{ textDecoration: 'none', textAlign: 'center' }}
                      >
                        .SRT
                      </a>
                    </div>
                    <button className="delete-button" style={{ marginTop: 12 }} disabled={deleting === p.id} onClick={() => handleDeleteProject(p.id)}>
                      {deleting === p.id ? 'Deleting…' : 'Delete video & all files'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 9: SETTINGS & HARDWARE */}
        {/* ============================================================== */}
        {activeTab === 'settings' && (
          <div className="create-panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">ENVIRONMENT CONFIGURATION</div>
                <h2>Models & Production Settings</h2>
                <p>Choose local inference or your FreeLLMAPI desktop models, with local rendering.</p>
              </div>
            </div>

            <ModelSettings api={API} onSaved={fetchHealth} />
            <div className="setting-row"><div><strong>Offline narration</strong><p>Kokoro speech with measured timing, restrained pitch and pacing adjustments.</p></div></div>
            <div className="setting-row"><div><strong>Renderer</strong><p>Claude-generated Canvas scenes · Chromium · FFmpeg. Video completion requires quality checks to pass.</p></div></div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PAGE 10: DIAGNOSTICS LOG */}
        {/* ============================================================== */}
        {activeTab === 'logs' && (
          <div className="create-panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">LIVE TELEMETRY</div>
                <h2>System Health & Diagnostics Log</h2>
                <p>Real-time telemetry from /api/health</p>
              </div>
              <button className="secondary-button" onClick={fetchHealth}>
                Refresh Health
              </button>
            </div>

            <pre className="log-viewer">
              {JSON.stringify(health, null, 2)}
            </pre>
          </div>
        )}

        {/* Studio Footer */}
        <footer>
          CSRGO AI VIDEO STUDIO · RESEARCH-DRIVEN CINEMATIC UPGRADE
          <span>Free model options · local rendering · source-backed storytelling</span>
        </footer>
      </main>
    </div>
  );
}
