import sys
import os
import random
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError("openenv is required. Install with: pip install openenv-core") from e

try:
    from ..models import EmailTriageAction, EmailTriageObservation
    from .email_triage_env_environment import EmailTriageEnvironment, TASKS
except (ModuleNotFoundError, ImportError):
    from models import EmailTriageAction, EmailTriageObservation
    from server.email_triage_env_environment import EmailTriageEnvironment, TASKS

from fastapi.responses import JSONResponse, HTMLResponse

app = create_app(
    EmailTriageEnvironment,
    EmailTriageAction,
    EmailTriageObservation,
    env_name="email_triage_env",
    max_concurrent_envs=10,
)


# ── Live Demo UI ───────────────────────────────────────────────────────────────

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Email Triage Environment — Live Demo</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg: #0a0e17;
    --surface: #111827;
    --surface2: #1a2234;
    --border: #1e2d45;
    --accent: #00d4ff;
    --accent2: #7c3aed;
    --green: #10b981;
    --yellow: #f59e0b;
    --red: #ef4444;
    --text: #e2e8f0;
    --muted: #64748b;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Animated grid background */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    opacity: 0.3;
    z-index: 0;
    pointer-events: none;
  }

  .container {
    position: relative;
    z-index: 1;
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
  }

  /* Header */
  .header {
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .header-left h1 {
    font-family: var(--mono);
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.02em;
  }

  .header-left p {
    color: var(--muted);
    font-size: 0.85rem;
    margin-top: 0.3rem;
    font-family: var(--mono);
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.75rem;
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .badge-live { background: rgba(16,185,129,0.15); color: var(--green); border: 1px solid rgba(16,185,129,0.3); }
  .badge-openenv { background: rgba(0,212,255,0.1); color: var(--accent); border: 1px solid rgba(0,212,255,0.2); }

  .badges { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; margin-top: 0.5rem; }

  /* Status bar */
  .status-bar {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    display: flex;
    gap: 2rem;
    margin-bottom: 2rem;
    flex-wrap: wrap;
  }

  .stat { display: flex; flex-direction: column; gap: 0.2rem; }
  .stat-label { font-family: var(--mono); font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
  .stat-value { font-family: var(--mono); font-size: 1.1rem; font-weight: 600; color: var(--text); }
  .stat-value.accent { color: var(--accent); }
  .stat-value.green { color: var(--green); }

  /* Main grid */
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }

  /* Cards */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }

  .card-header {
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .card-body { padding: 1.25rem; }

  /* Email display */
  .email-field { margin-bottom: 1rem; }
  .email-field:last-child { margin-bottom: 0; }
  .field-label {
    font-family: var(--mono);
    font-size: 0.65rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.35rem;
  }
  .field-value {
    font-size: 0.9rem;
    color: var(--text);
    line-height: 1.5;
  }
  .field-value.subject {
    font-family: var(--mono);
    font-weight: 600;
    color: var(--accent);
    font-size: 0.95rem;
  }
  .field-value.body {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.75rem;
    font-size: 0.85rem;
    line-height: 1.6;
    max-height: 140px;
    overflow-y: auto;
  }
  .field-value.sender {
    font-family: var(--mono);
    font-size: 0.82rem;
    color: var(--muted);
  }

  /* Difficulty pill */
  .difficulty-pill {
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
  }
  .diff-easy   { background: rgba(16,185,129,0.15); color: var(--green); }
  .diff-medium { background: rgba(245,158,11,0.15);  color: var(--yellow); }
  .diff-hard   { background: rgba(239,68,68,0.15);   color: var(--red); }
  .diff-none   { background: rgba(100,116,139,0.15); color: var(--muted); }

  /* Action form */
  .form-group { margin-bottom: 1rem; }
  .form-group:last-of-type { margin-bottom: 1.25rem; }

  label {
    display: block;
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
  }

  select, input[type=number], textarea {
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 0.85rem;
    padding: 0.55rem 0.75rem;
    outline: none;
    transition: border-color 0.15s;
    appearance: none;
  }

  select:focus, input:focus, textarea:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(0,212,255,0.1);
  }

  textarea { resize: vertical; min-height: 70px; }

  /* Buttons */
  .btn-row { display: flex; gap: 0.75rem; }

  button {
    font-family: var(--mono);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border: none;
    border-radius: 4px;
    padding: 0.65rem 1.25rem;
    cursor: pointer;
    transition: all 0.15s;
    flex: 1;
  }

  .btn-primary {
    background: var(--accent);
    color: #0a0e17;
  }
  .btn-primary:hover { background: #00b8d9; transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

  .btn-secondary {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover { border-color: var(--accent); color: var(--accent); }

  /* Reward breakdown */
  .reward-display {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 1rem;
  }

  .total-score {
    font-family: var(--mono);
    font-size: 2rem;
    font-weight: 600;
    color: var(--accent);
    text-align: center;
    margin-bottom: 0.25rem;
  }
  .total-label {
    font-family: var(--mono);
    font-size: 0.65rem;
    color: var(--muted);
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 1rem;
  }

  .breakdown-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.6rem;
  }
  .breakdown-row:last-child { margin-bottom: 0; }

  .breakdown-name {
    font-family: var(--mono);
    font-size: 0.72rem;
    color: var(--muted);
    width: 110px;
    flex-shrink: 0;
  }

  .bar-track {
    flex: 1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s cubic-bezier(0.4,0,0.2,1);
  }

  .bar-classification { background: var(--accent); }
  .bar-priority       { background: var(--accent2); }
  .bar-reply          { background: var(--green); }

  .breakdown-val {
    font-family: var(--mono);
    font-size: 0.72rem;
    color: var(--text);
    width: 36px;
    text-align: right;
    flex-shrink: 0;
  }

  /* Feedback box */
  .feedback-box {
    background: var(--surface2);
    border-left: 3px solid var(--accent);
    border-radius: 0 4px 4px 0;
    padding: 0.75rem 1rem;
    font-family: var(--mono);
    font-size: 0.8rem;
    color: var(--text);
    line-height: 1.5;
    word-break: break-word;
  }

  .feedback-box.done {
    border-left-color: var(--green);
  }

  /* Episode log */
  .log-entry {
    border-bottom: 1px solid var(--border);
    padding: 0.65rem 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-family: var(--mono);
    font-size: 0.78rem;
  }
  .log-entry:last-child { border-bottom: none; }

  .log-step { color: var(--muted); width: 40px; flex-shrink: 0; }
  .log-class { color: var(--text); flex: 1; }
  .log-score { font-weight: 600; width: 40px; text-align: right; flex-shrink: 0; }

  .score-high   { color: var(--green); }
  .score-mid    { color: var(--yellow); }
  .score-low    { color: var(--red); }

  /* Empty state */
  .empty {
    text-align: center;
    padding: 2rem 1rem;
    color: var(--muted);
    font-family: var(--mono);
    font-size: 0.8rem;
  }
  .empty-icon { font-size: 2rem; margin-bottom: 0.5rem; }

  /* Thread context */
  .thread-context {
    background: rgba(124,58,237,0.08);
    border: 1px solid rgba(124,58,237,0.25);
    border-radius: 4px;
    padding: 0.75rem;
    margin-bottom: 1rem;
    font-family: var(--mono);
    font-size: 0.75rem;
    color: #a78bfa;
    line-height: 1.6;
  }
  .thread-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #7c3aed;
    margin-bottom: 0.4rem;
  }

  /* Adversarial warning */
  .adversarial-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.6rem;
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 0.65rem;
    color: var(--red);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  /* Loading spinner */
  .spinner {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 0.4rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Done banner */
  .done-banner {
    background: rgba(16,185,129,0.1);
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
    font-family: var(--mono);
    color: var(--green);
    margin-bottom: 1rem;
  }
  .done-banner .big { font-size: 1.5rem; font-weight: 600; }

  /* Full-width card */
  .card-full { grid-column: 1 / -1; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* Fade in */
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .card { animation: fadeUp 0.3s ease both; }
  .card:nth-child(2) { animation-delay: 0.05s; }
  .card:nth-child(3) { animation-delay: 0.1s; }
  .card:nth-child(4) { animation-delay: 0.15s; }
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <div class="header-left">
      <h1>📬 email_triage_env</h1>
      <p>OpenEnv · Real-World RL Environment · Meta PyTorch × Scaler Hackathon 2026</p>
      <div class="badges">
        <span class="badge badge-live">● Live</span>
        <span class="badge badge-openenv">OpenEnv v1</span>
      </div>
    </div>
  </div>

  <div class="status-bar">
    <div class="stat">
      <span class="stat-label">Episode</span>
      <span class="stat-value accent" id="ep-num">—</span>
    </div>
    <div class="stat">
      <span class="stat-label">Step</span>
      <span class="stat-value" id="ep-step">0 / 3</span>
    </div>
    <div class="stat">
      <span class="stat-label">Cumulative Reward</span>
      <span class="stat-value green" id="ep-reward">0.000</span>
    </div>
    <div class="stat">
      <span class="stat-label">Difficulty</span>
      <span class="stat-value" id="ep-diff">—</span>
    </div>
    <div class="stat">
      <span class="stat-label">Status</span>
      <span class="stat-value" id="ep-status">Not started</span>
    </div>
  </div>

  <div class="grid">

    <!-- Email panel -->
    <div class="card">
      <div class="card-header">
        <span>Current Email</span>
        <span id="diff-pill" class="difficulty-pill diff-none">—</span>
      </div>
      <div class="card-body" id="email-panel">
        <div class="empty">
          <div class="empty-icon">📭</div>
          <div>Click "Start Episode" to begin</div>
        </div>
      </div>
    </div>

    <!-- Action panel -->
    <div class="card">
      <div class="card-header">
        <span>Agent Action</span>
        <span id="action-hint" style="font-size:0.65rem;color:var(--muted)">fill in your triage decision</span>
      </div>
      <div class="card-body">
        <div class="form-group">
          <label>Classification</label>
          <select id="classification">
            <option value="spam">spam</option>
            <option value="urgent">urgent</option>
            <option value="normal" selected>normal</option>
            <option value="newsletter">newsletter</option>
          </select>
        </div>
        <div class="form-group">
          <label>Priority (1 = lowest, 5 = highest)</label>
          <input type="number" id="priority" min="1" max="5" value="3"/>
        </div>
        <div class="form-group">
          <label>Suggested Reply (or "no_reply")</label>
          <textarea id="reply" placeholder="no_reply">no_reply</textarea>
        </div>
        <div class="btn-row">
          <button class="btn-primary" id="btn-reset" onclick="startEpisode()">Start Episode</button>
          <button class="btn-primary" id="btn-step" onclick="submitStep()" disabled>Submit →</button>
        </div>
      </div>
    </div>

    <!-- Reward panel -->
    <div class="card">
      <div class="card-header">Reward Breakdown</div>
      <div class="card-body" id="reward-panel">
        <div class="empty">
          <div class="empty-icon">📊</div>
          <div>Reward breakdown appears after each step</div>
        </div>
      </div>
    </div>

    <!-- Episode log -->
    <div class="card">
      <div class="card-header">
        <span>Episode Log</span>
        <span id="log-count" style="font-size:0.65rem;color:var(--muted)">0 steps</span>
      </div>
      <div class="card-body" id="log-panel">
        <div class="empty">
          <div class="empty-icon">📋</div>
          <div>Steps will appear here</div>
        </div>
      </div>
    </div>

  </div><!-- /grid -->
</div><!-- /container -->

<script>
  const BASE = '';
  let sessionId = null;
  let step = 0;
  let cumReward = 0;
  let difficulty = 'easy';
  let logEntries = [];
  const DIFF_ORDER = ['easy','medium','hard'];

  async function startEpisode() {
    document.getElementById('btn-reset').disabled = true;
    document.getElementById('btn-reset').innerHTML = '<span class="spinner"></span>Starting...';

    step = 0; cumReward = 0; logEntries = [];
    difficulty = 'easy';
    updateStatus('Running', '#f59e0b');
    document.getElementById('ep-reward').textContent = '0.000';
    document.getElementById('ep-step').textContent = '0 / 3';
    document.getElementById('log-panel').innerHTML = '<div class="empty"><div class="empty-icon">📋</div><div>Steps will appear here</div></div>';
    document.getElementById('reward-panel').innerHTML = '<div class="empty"><div class="empty-icon">📊</div><div>Reward breakdown appears after each step</div></div>';

    try {
      const r = await fetch(BASE + '/reset', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
      const data = await r.json();
      const obs = data.observation || data;
      sessionId = data.session_id || null;
      renderEmail(obs, 'easy');
      document.getElementById('ep-num').textContent = '#' + Date.now().toString().slice(-4);
      document.getElementById('ep-diff').textContent = 'easy';
      document.getElementById('btn-step').disabled = false;
      updateStatus('Active', 'var(--green)');
    } catch(e) {
      alert('Error connecting to environment: ' + e.message);
    }

    document.getElementById('btn-reset').disabled = false;
    document.getElementById('btn-reset').innerHTML = 'Restart';
  }

  async function submitStep() {
    const classification = document.getElementById('classification').value;
    const priority = parseInt(document.getElementById('priority').value);
    const suggested_reply = document.getElementById('reply').value.trim() || 'no_reply';

    document.getElementById('btn-step').disabled = true;
    document.getElementById('btn-step').innerHTML = '<span class="spinner"></span>Grading...';

    const body = { action: { classification, priority, suggested_reply } };
    if (sessionId) body.session_id = sessionId;

    try {
      const r = await fetch(BASE + '/step', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      const data = await r.json();
      const obs = data.observation || data;
      const reward = data.reward ?? obs.reward ?? obs.score ?? 0;
      const done = data.done ?? obs.done ?? false;
      const breakdown = obs.reward_breakdown || null;
      const feedback = obs.feedback || '';

      step++;
      cumReward += reward;

      // Determine next difficulty
      if (!done) {
        const idx = DIFF_ORDER.indexOf(difficulty);
        difficulty = DIFF_ORDER[Math.min(idx + 1, 2)];
      }

      document.getElementById('ep-step').textContent = step + ' / 3';
      document.getElementById('ep-reward').textContent = cumReward.toFixed(3);
      document.getElementById('ep-diff').textContent = done ? 'complete' : difficulty;

      // Log entry
      logEntries.push({ step, classification, priority, reward });
      renderLog();

      // Reward breakdown
      renderReward(reward, breakdown, feedback, done);

      if (done) {
        renderDone(cumReward);
        document.getElementById('btn-step').disabled = true;
        document.getElementById('btn-step').innerHTML = 'Submit →';
        document.getElementById('btn-reset').innerHTML = 'New Episode';
        updateStatus('Done ✓', 'var(--green)');
      } else {
        renderEmail(obs, difficulty);
        document.getElementById('btn-step').disabled = false;
        document.getElementById('btn-step').innerHTML = 'Submit →';
      }
    } catch(e) {
      alert('Error: ' + e.message);
      document.getElementById('btn-step').disabled = false;
      document.getElementById('btn-step').innerHTML = 'Submit →';
    }
  }

  function renderEmail(obs, diff) {
    const diffClass = {'easy':'diff-easy','medium':'diff-medium','hard':'diff-hard'}[diff] || 'diff-none';
    document.getElementById('diff-pill').className = 'difficulty-pill ' + diffClass;
    document.getElementById('diff-pill').textContent = diff || '—';

    const taskDesc = obs.task_description || '';
    const hasThread = taskDesc.includes('THREAD CONTEXT');
    let threadHTML = '';
    if (hasThread) {
      const match = taskDesc.match(/--- THREAD CONTEXT.*?---([\s\S]*?)--- END THREAD/);
      if (match) {
        threadHTML = `<div class="thread-context"><div class="thread-label">🧵 Thread Context</div>${escHtml(match[1].trim())}</div>`;
      }
    }

    document.getElementById('email-panel').innerHTML = `
      ${threadHTML}
      <div class="email-field">
        <div class="field-label">From</div>
        <div class="field-value sender">${escHtml(obs.sender || '—')}</div>
      </div>
      <div class="email-field">
        <div class="field-label">Subject</div>
        <div class="field-value subject">${escHtml(obs.email_subject || '—')}</div>
      </div>
      <div class="email-field">
        <div class="field-label">Body</div>
        <div class="field-value body">${escHtml(obs.email_body || '—')}</div>
      </div>
    `;
  }

  function renderReward(reward, breakdown, feedback, done) {
    const scoreColor = reward >= 0.8 ? 'var(--green)' : reward >= 0.5 ? 'var(--yellow)' : 'var(--red)';

    let breakdownHTML = '';
    if (breakdown) {
      const cls = breakdown.classification ?? 0;
      const pri = breakdown.priority ?? 0;
      const rep = breakdown.reply_quality ?? 0;
      breakdownHTML = `
        <div class="breakdown-row">
          <span class="breakdown-name">Classification</span>
          <div class="bar-track"><div class="bar-fill bar-classification" style="width:${(cls/0.5)*100}%"></div></div>
          <span class="breakdown-val">${cls.toFixed(2)}</span>
        </div>
        <div class="breakdown-row">
          <span class="breakdown-name">Priority</span>
          <div class="bar-track"><div class="bar-fill bar-priority" style="width:${(pri/0.3)*100}%"></div></div>
          <span class="breakdown-val">${pri.toFixed(2)}</span>
        </div>
        <div class="breakdown-row">
          <span class="breakdown-name">Reply Quality</span>
          <div class="bar-track"><div class="bar-fill bar-reply" style="width:${(rep/0.2)*100}%"></div></div>
          <span class="breakdown-val">${rep.toFixed(2)}</span>
        </div>
      `;
    }

    document.getElementById('reward-panel').innerHTML = `
      <div class="reward-display">
        <div class="total-score" style="color:${scoreColor}">${reward.toFixed(2)}</div>
        <div class="total-label">Step Reward</div>
        ${breakdownHTML}
      </div>
      <div class="feedback-box ${done ? 'done' : ''}">${escHtml(feedback)}</div>
    `;
  }

  function renderDone(total) {
    const avg = (total / 3).toFixed(3);
    const panel = document.getElementById('reward-panel');
    panel.innerHTML = `<div class="done-banner">
      <div class="big">Episode Complete</div>
      <div style="margin-top:0.4rem;font-size:0.8rem">Total Reward: ${total.toFixed(3)} &nbsp;·&nbsp; Avg: ${avg}</div>
    </div>` + panel.innerHTML;
  }

  function renderLog() {
    if (logEntries.length === 0) return;
    document.getElementById('log-count').textContent = logEntries.length + ' step' + (logEntries.length > 1 ? 's' : '');
    document.getElementById('log-panel').innerHTML = logEntries.map(e => {
      const sc = e.reward >= 0.8 ? 'score-high' : e.reward >= 0.5 ? 'score-mid' : 'score-low';
      return `<div class="log-entry">
        <span class="log-step">S${e.step}</span>
        <span class="log-class">${e.classification} · p${e.priority}</span>
        <span class="log-score ${sc}">${e.reward.toFixed(2)}</span>
      </div>`;
    }).join('');
  }

  function updateStatus(text, color) {
    const el = document.getElementById('ep-status');
    el.textContent = text;
    el.style.color = color;
  }

  function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def demo_ui():
    """Live interactive demo — judges can triage emails in the browser."""
    return DEMO_HTML


# ── /benchmark endpoint ────────────────────────────────────────────────────────

@app.get("/benchmark")
def benchmark():
    """
    Run a deterministic benchmark across ALL tasks in all difficulty levels.
    Uses a perfect oracle agent to show the maximum achievable score per task,
    and a naive baseline to show the floor. Returns a structured report.
    """
    random.seed(42)

    env = EmailTriageEnvironment()
    results = {}
    total_tasks = 0
    total_oracle_score = 0.0

    for difficulty, task_list in TASKS.items():
        difficulty_results = []

        for task in task_list:
            total_tasks += 1

            # ── Oracle agent (perfect answer) ────────────────────────────────
            oracle_action = EmailTriageAction(
                classification=task["correct_classification"],
                priority=task["correct_priority"],
                suggested_reply=(
                    " ".join(task.get("required_reply_keywords", []))
                    + " I authorize this action and confirm the request."
                    if task.get("needs_reply")
                    else "no_reply"
                ),
            )
            oracle_score, oracle_breakdown = env._grade_action(oracle_action, task)

            # ── Naive baseline agent (always guesses normal/3/no_reply) ──────
            naive_action = EmailTriageAction(
                classification="normal",
                priority=3,
                suggested_reply="no_reply",
            )
            naive_score, naive_breakdown = env._grade_action(naive_action, task)

            total_oracle_score += oracle_score

            difficulty_results.append({
                "email_subject":          task["email_subject"],
                "sender":                 task["sender"],
                "correct_classification": task["correct_classification"],
                "correct_priority":       task["correct_priority"],
                "adversarial":            task.get("adversarial", False),
                "has_thread_context":     bool(task.get("thread_context")),
                "oracle_score":           oracle_score,
                "oracle_breakdown":       oracle_breakdown,
                "naive_score":            naive_score,
                "naive_breakdown":        naive_breakdown,
                "improvement_headroom":   round(oracle_score - naive_score, 2),
            })

        results[difficulty] = {
            "tasks":            difficulty_results,
            "avg_oracle_score": round(sum(t["oracle_score"] for t in difficulty_results) / len(difficulty_results), 3),
            "avg_naive_score":  round(sum(t["naive_score"]  for t in difficulty_results) / len(difficulty_results), 3),
        }

    return JSONResponse({
        "benchmark": "email_triage_env",
        "version":   "2.0.0",
        "seed":      42,
        "total_tasks": total_tasks,
        "overall_oracle_avg": round(total_oracle_score / total_tasks, 3),
        "summary": {
            diff: {
                "avg_oracle": results[diff]["avg_oracle_score"],
                "avg_naive":  results[diff]["avg_naive_score"],
                "task_count": len(results[diff]["tasks"]),
            }
            for diff in results
        },
        "details": results,
        "note": (
            "oracle = perfect agent that always gives the correct answer. "
            "naive = baseline agent that always answers normal/3/no_reply. "
            "A trained LLM agent should score between naive and oracle."
        ),
    })


# ── /info endpoint ─────────────────────────────────────────────────────────────

@app.get("/info")
def info():
    return JSONResponse({
        "name": "email_triage_env",
        "version": "2.0.0",
        "description": (
            "Real-world email triage environment. Agent learns to classify emails, "
            "assign priority, and generate replies across 3 difficulty levels. "
            "Features adversarial emails, thread context, and granular reward_breakdown."
        ),
        "difficulty_levels": ["easy", "medium", "hard"],
        "episode_steps": 3,
        "reward_range": [0.0, 1.0],
        "reward_components": {
            "classification": "0.0 – 0.50",
            "priority":       "0.0 – 0.30",
            "reply_quality":  "0.0 – 0.20",
        },
        "action_space": {
            "classification":  "str: spam | urgent | normal | newsletter",
            "priority":        "int: 1 (lowest) – 5 (highest)",
            "suggested_reply": "str: reply text or 'no_reply'",
        },
        "observation_space": {
            "email_subject":    "str",
            "email_body":       "str",
            "sender":           "str",
            "task_description": "str (includes thread context when relevant)",
            "feedback":         "str (score breakdown after each step)",
            "score":            "float 0.0–1.0",
            "reward":           "float 0.0–1.0",
            "done":             "bool",
            "reward_breakdown": "dict | null",
        },
        "special_features": [
            "Adversarial emails (4 types)",
            "Thread context injection",
            "Granular reward_breakdown per step",
            "Partial credit grading",
            "Live demo UI at /",
            "Full benchmark at /benchmark",
        ],
        "endpoints": {
            "/":          "Live interactive demo UI",
            "/reset":     "POST — start new episode",
            "/step":      "POST — submit action, get reward",
            "/state":     "GET  — current episode state",
            "/info":      "GET  — environment metadata",
            "/tasks":     "GET  — full task bank",
            "/benchmark": "GET  — oracle vs naive benchmark report",
            "/health":    "GET  — health check",
        },
    })


# ── /tasks endpoint ────────────────────────────────────────────────────────────

@app.get("/tasks")
def list_tasks():
    summary = {}
    for difficulty, task_list in TASKS.items():
        summary[difficulty] = [
            {
                "email_subject":           t["email_subject"],
                "sender":                  t["sender"],
                "correct_classification":  t["correct_classification"],
                "correct_priority":        t["correct_priority"],
                "needs_reply":             t.get("needs_reply", False),
                "adversarial":             t.get("adversarial", False),
                "has_thread_context":      bool(t.get("thread_context")),
                "required_reply_keywords": t.get("required_reply_keywords", []),
            }
            for t in task_list
        ]
    return JSONResponse({
        "total_tasks":          sum(len(v) for v in TASKS.values()),
        "tasks_by_difficulty":  summary,
    })


# ── Server entry point ─────────────────────────────────────────────────────────

def main(host: str = "0.0.0.0", port: int = 7860):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    main(port=args.port)