import React, { useEffect, useState } from 'react';

export default function ModelSettings({ api, onSaved }) {
  const [config, setConfig] = useState(null);
  const [models, setModels] = useState([]);
  const [key, setKey] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function request(path, options) {
    const response = await fetch(`${api}/api${path}`, options);
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request failed. Check your settings.');
    return result;
  }
  useEffect(() => { request('/ai/settings').then(setConfig).catch(e => setError(e.message)); }, []);
  function changeProvider(provider) {
    setConfig(c => ({ ...c, provider,
      endpoint: provider === 'ollama' ? 'http://127.0.0.1:11434' : 'http://127.0.0.1:31415',
      planning_model: provider === 'ollama' ? 'qwen3:1.7b' : 'auto',
      coding_model: provider === 'ollama' ? 'qwen2.5-coder:3b' : 'auto' }));
    setModels([]); setMessage(''); setError('');
  }
  async function save(test = false) {
    setBusy(true); setError(''); setMessage('');
    try {
      const { provider, endpoint, planning_model, coding_model, api_key_env, timeout_seconds } = config;
      const saved = await request('/ai/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, endpoint, planning_model, coding_model, api_key_env, timeout_seconds }) });
      if (key) {
        await request('/ai/credential', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: key }) });
        setKey(''); saved.api_key_present = true;
      }
      setConfig(saved);
      if (test) { await request('/ai/initialize', { method: 'POST' }); setMessage('Connection verified through Claude Code.'); }
      else setMessage('Model settings saved.');
      onSaved?.();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function loadModels() {
    setBusy(true); setError('');
    try { const data = await request('/models'); setModels((data.models || []).map(m => m.model || m.name)); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  if (!config) return <p role="status">{error || 'Loading model settings…'}</p>;
  return <section className="model-settings">
    <div className="section-heading"><div><div className="eyebrow">MODEL CONNECTION</div><h2>Choose your model source</h2>
      <p>Claude Code researches, writes and generates animation code with your selected models.</p>
    </div><span className="badge-tag">Claude Code engine</span></div>
    <div className="provider-choices" role="group" aria-label="Model source">
      <button className={config.provider === 'ollama' ? 'provider-choice selected' : 'provider-choice'} onClick={() => changeProvider('ollama')}>
        <strong>Ollama</strong><span>Local models · private inference · no API fee</span></button>
      <button className={config.provider === 'freellmapi' ? 'provider-choice selected' : 'provider-choice'} onClick={() => changeProvider('freellmapi')}>
        <strong>FreeLLMAPI</strong><span>Your installed FreeLLMAPI desktop · Internet and API key required</span></button>
    </div>
    {config.provider === 'freellmapi' && <p className="connection-hint">Desktop endpoint: http://127.0.0.1:31415. Run the studio backend on that same PC. Use the server root URL; /v1 is added automatically.</p>}
    <div className="form-grid-2">
      <label className="field-label">{config.provider === 'ollama' ? 'Ollama endpoint' : 'API endpoint'}
        <input value={config.endpoint} onChange={e => setConfig(c => ({ ...c, endpoint: e.target.value }))} /></label>
      <label className="field-label">Request timeout (seconds)<input type="number" min="30" max="600" value={config.timeout_seconds}
        onChange={e => setConfig(c => ({ ...c, timeout_seconds: Number(e.target.value) }))} /></label>
      <label className="field-label">Research and story model<input list="provider-models" value={config.planning_model}
        onChange={e => setConfig(c => ({ ...c, planning_model: e.target.value }))} /></label>
      <label className="field-label">Animation coding model<input list="provider-models" value={config.coding_model}
        onChange={e => setConfig(c => ({ ...c, coding_model: e.target.value }))} /></label>
    </div>
    <datalist id="provider-models">{models.map(m => <option key={m} value={m} />)}</datalist>
    {config.provider === 'freellmapi' && <div className="credential-panel">
      <p>Use <code>auto</code>, <code>auto:smart</code>, a named routing profile, or any available model from your FreeLLMAPI catalog. Provider keys and free-tier limits are managed in FreeLLMAPI.</p>
      <label className="field-label">API key for this backend session
        <input type="password" autoComplete="off" value={key} placeholder={config.api_key_present ? 'A key is already configured' : 'Paste your FreeLLMAPI unified key'} onChange={e => setKey(e.target.value)} />
      </label><small>The key stays in backend memory and is cleared when it restarts. For a persistent connection, set {config.api_key_env} in your backend environment.</small>
    </div>}
    {error && <div className="error-box" role="alert">{error}</div>}
    {message && <p className="good" role="status">{message}</p>}
    <div className="settings-actions">
      <button disabled={busy} className="primary-button" onClick={() => save(false)}>{busy ? 'Working…' : 'Save model settings'}</button>
      <button disabled={busy} className="secondary-button" onClick={() => save(true)}>Save & test connection</button>
      <button disabled={busy} className="text-button" onClick={loadModels}>Load models from saved source</button>
    </div>
  </section>;
}
