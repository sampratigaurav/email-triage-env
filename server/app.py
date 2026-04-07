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
<title>Email Triage Environment</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:       #070b11;
  --panel:    #0d1520;
  --panel2:   #111d2e;
  --border:   #1a2c42;
  --border2:  #243d57;
  --blue:     #3b82f6;
  --cyan:     #06b6d4;
  --green:    #22c55e;
  --amber:    #f59e0b;
  --red:      #ef4444;
  --purple:   #8b5cf6;
  --text:     #f1f5f9;
  --muted:    #475569;
  --muted2:   #64748b;
  --mono:     'JetBrains Mono', monospace;
  --display:  'Syne', sans-serif;
}

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--mono);
  min-height: 100vh;
  overflow-x: hidden;
}

/* Subtle dot grid */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background-image: radial-gradient(circle, #1e3a5f22 1px, transparent 1px);
  background-size: 32px 32px;
  pointer-events: none;
  z-index: 0;
}

.wrap {
  position: relative;
  z-index: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1.5rem 5rem;
}

/* ── Header ── */
.hdr {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.hdr-title {
  font-family: var(--display);
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  background: linear-gradient(135deg, var(--cyan) 0%, var(--blue) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hdr-sub {
  font-size: 0.72rem;
  color: var(--muted2);
  margin-top: 0.3rem;
  letter-spacing: 0.05em;
}

.hdr-tags { display: flex; gap: 0.5rem; margin-top: 0.6rem; flex-wrap: wrap; }

.tag {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.25rem 0.65rem;
  border-radius: 3px;
}

.tag-live   { background: rgba(34,197,94,.12);  color: var(--green);  border: 1px solid rgba(34,197,94,.3); }
.tag-oe     { background: rgba(59,130,246,.1);  color: var(--blue);   border: 1px solid rgba(59,130,246,.25); }
.tag-ws     { background: rgba(139,92,246,.1);  color: var(--purple); border: 1px solid rgba(139,92,246,.25); }
.tag-ws.connecting { color: var(--amber); border-color: rgba(245,158,11,.3); background: rgba(245,158,11,.08); }
.tag-ws.error      { color: var(--red);   border-color: rgba(239,68,68,.3);  background: rgba(239,68,68,.08); }

.hdr-links { display: flex; gap: 0.75rem; align-items: center; }
.hdr-link {
  font-size: 0.7rem;
  color: var(--muted2);
  text-decoration: none;
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  transition: all .15s;
}
.hdr-link:hover { color: var(--cyan); border-color: var(--cyan); }

/* ── Stats strip ── */
.stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.stat {
  background: var(--panel);
  padding: 0.85rem 1rem;
}

.stat-l {
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  margin-bottom: 0.3rem;
}

.stat-v {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
}

.stat-v.cyan   { color: var(--cyan); }
.stat-v.green  { color: var(--green); }
.stat-v.amber  { color: var(--amber); }
.stat-v.red    { color: var(--red); }

/* ── Progress bar ── */
.progress-wrap {
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.progress-track {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--blue), var(--cyan));
  border-radius: 2px;
  transition: width .4s ease;
  width: 0%;
}

.step-dots { display: flex; gap: 0.5rem; }
.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--muted);
  transition: all .2s;
}
.step-dot.done   { border-color: var(--green); color: var(--green); background: rgba(34,197,94,.1); }
.step-dot.active { border-color: var(--cyan);  color: var(--cyan);  background: rgba(6,182,212,.1); }

/* ── Main grid ── */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
.full { grid-column: 1 / -1; }

/* ── Panel ── */
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.panel-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--panel2);
}

.panel-title {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted2);
}

.panel-badge {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  border-radius: 3px;
}

.pb-easy   { background: rgba(34,197,94,.12);  color: var(--green); }
.pb-medium { background: rgba(245,158,11,.12); color: var(--amber); }
.pb-hard   { background: rgba(239,68,68,.12);  color: var(--red); }
.pb-none   { background: rgba(71,85,105,.1);   color: var(--muted); }

.panel-body { padding: 1.1rem; }

/* ── Email display ── */
.email-meta {
  font-size: 0.72rem;
  color: var(--muted2);
  margin-bottom: 0.25rem;
  letter-spacing: 0.04em;
}

.email-sender {
  font-size: 0.8rem;
  color: var(--muted2);
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
}

.email-subject {
  font-family: var(--display);
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.85rem;
  line-height: 1.3;
}

.email-body-wrap {
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.85rem;
  font-size: 0.8rem;
  line-height: 1.7;
  color: #94a3b8;
  max-height: 150px;
  overflow-y: auto;
}

/* Thread context */
.thread-ctx {
  margin-bottom: 0.85rem;
  background: rgba(139,92,246,.06);
  border: 1px solid rgba(139,92,246,.2);
  border-radius: 6px;
  padding: 0.75rem;
}

.thread-ctx-hdr {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--purple);
  margin-bottom: 0.5rem;
}

.thread-ctx-body {
  font-size: 0.75rem;
  color: #a78bfa;
  line-height: 1.6;
}

/* ── Form ── */
.diff-selector {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.diff-btn {
  padding: 0.55rem;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted2);
  font-family: var(--mono);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all .15s;
  text-align: center;
}

.diff-btn:hover { border-color: var(--border2); color: var(--text); }
.diff-btn.active-easy   { background: rgba(34,197,94,.1);  border-color: var(--green); color: var(--green); }
.diff-btn.active-medium { background: rgba(245,158,11,.1); border-color: var(--amber); color: var(--amber); }
.diff-btn.active-hard   { background: rgba(239,68,68,.1);  border-color: var(--red);   color: var(--red); }

.diff-note {
  font-size: 0.65rem;
  color: var(--muted);
  margin-bottom: 1rem;
  text-align: center;
}

.field { margin-bottom: 0.85rem; }

.field-label {
  display: block;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 0.35rem;
}

select, input[type=number], textarea {
  width: 100%;
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 5px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 0.82rem;
  padding: 0.55rem 0.75rem;
  outline: none;
  transition: border-color .15s, box-shadow .15s;
  appearance: none;
}

select:focus, input:focus, textarea:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(59,130,246,.12);
}

textarea { resize: vertical; min-height: 64px; }

.btn-row { display: flex; gap: 0.65rem; margin-top: 1rem; }

.btn {
  flex: 1;
  padding: 0.7rem 1rem;
  border-radius: 6px;
  border: none;
  font-family: var(--mono);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  transition: all .15s;
}

.btn:disabled { opacity: 0.35; cursor: not-allowed; }

.btn-primary {
  background: linear-gradient(135deg, var(--blue), var(--cyan));
  color: #fff;
}
.btn-primary:hover:not(:disabled) { opacity: 0.88; transform: translateY(-1px); }

.btn-ghost {
  background: transparent;
  color: var(--muted2);
  border: 1px solid var(--border);
}
.btn-ghost:hover:not(:disabled) { border-color: var(--border2); color: var(--text); }

/* ── Reward breakdown ── */
.score-big {
  font-family: var(--display);
  font-size: 2.8rem;
  font-weight: 800;
  text-align: center;
  line-height: 1;
  margin-bottom: 0.2rem;
}

.score-label {
  font-size: 0.6rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  text-align: center;
  margin-bottom: 1.25rem;
}

.bd-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}

.bd-label {
  font-size: 0.65rem;
  color: var(--muted2);
  width: 100px;
  flex-shrink: 0;
}

.bd-track {
  flex: 1;
  height: 5px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.bd-fill {
  height: 100%;
  border-radius: 3px;
  transition: width .5s cubic-bezier(.4,0,.2,1);
  width: 0%;
}

.bd-val {
  font-size: 0.7rem;
  font-weight: 700;
  width: 34px;
  text-align: right;
  flex-shrink: 0;
}

/* ── Feedback ── */
.feedback {
  margin-top: 1rem;
  padding: 0.75rem 0.9rem;
  border-radius: 5px;
  font-size: 0.75rem;
  line-height: 1.6;
  color: #94a3b8;
  background: var(--panel2);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border2);
  word-break: break-word;
}

.feedback.good { border-left-color: var(--green); }
.feedback.bad  { border-left-color: var(--red); }

/* ── Episode log ── */
.log-row {
  display: grid;
  grid-template-columns: 28px 80px 1fr 60px;
  gap: 0.5rem;
  align-items: center;
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.72rem;
}
.log-row:last-child { border-bottom: none; }

.log-step   { color: var(--muted); text-align: center; }
.log-diff span {
  padding: 0.15rem 0.45rem;
  border-radius: 3px;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.log-action { color: #94a3b8; }
.log-score  { font-weight: 700; text-align: right; }

/* ── Empty state ── */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2.5rem 1rem;
  color: var(--muted);
  gap: 0.5rem;
}

.empty-icon { font-size: 2rem; }
.empty-text { font-size: 0.75rem; text-align: center; }

/* ── Done overlay ── */
.done-banner {
  background: rgba(34,197,94,.08);
  border: 1px solid rgba(34,197,94,.25);
  border-radius: 8px;
  padding: 1.25rem;
  text-align: center;
  margin-bottom: 1rem;
}

.done-banner h3 {
  font-family: var(--display);
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--green);
  margin-bottom: 0.3rem;
}

.done-banner p { font-size: 0.75rem; color: var(--muted2); }

/* ── Hint ── */
.hint-box {
  margin-top: 0.85rem;
  padding: 0.65rem 0.85rem;
  border-radius: 5px;
  font-size: 0.72rem;
  line-height: 1.6;
  background: rgba(245,158,11,.07);
  border: 1px solid rgba(245,158,11,.2);
  color: #fbbf24;
}

.hint-label {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 0.3rem;
  color: var(--amber);
}

/* spinner */
.spin {
  display: inline-block;
  width: 12px; height: 12px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: rot .6s linear infinite;
  vertical-align: middle;
  margin-right: 0.3rem;
}
@keyframes rot { to { transform: rotate(360deg); } }

/* ── Connection banner ── */
.conn-banner {
  display: none;
  text-align: center;
  padding: 0.6rem;
  font-size: 0.72rem;
  margin-bottom: 1rem;
  border-radius: 6px;
}
.conn-banner.show { display: block; }
.conn-banner.connecting { background: rgba(245,158,11,.1); border: 1px solid rgba(245,158,11,.25); color: var(--amber); }
.conn-banner.error      { background: rgba(239,68,68,.1);  border: 1px solid rgba(239,68,68,.25);  color: var(--red); }

/* scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.panel { animation: fadeUp .3s ease both; }
.panel:nth-child(2) { animation-delay: .06s; }
.panel:nth-child(3) { animation-delay: .12s; }
.panel:nth-child(4) { animation-delay: .18s; }
</style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div class="hdr">
    <div>
      <div class="hdr-title">📬 email_triage_env</div>
      <div class="hdr-sub">REAL-WORLD RL ENVIRONMENT · META PYTORCH × SCALER HACKATHON 2026</div>
      <div class="hdr-tags">
        <span class="tag tag-live">● Live</span>
        <span class="tag tag-oe">OpenEnv v1</span>
        <span class="tag tag-ws" id="ws-tag">⬡ WebSocket</span>
      </div>
    </div>
    <div class="hdr-links">
      <a class="hdr-link" href="/docs" target="_blank">API Docs</a>
      <a class="hdr-link" href="/benchmark" target="_blank">Benchmark</a>
      <a class="hdr-link" href="/tasks" target="_blank">Tasks</a>
    </div>
  </div>

  <!-- Connection banner -->
  <div class="conn-banner" id="conn-banner"></div>

  <!-- Stats strip -->
  <div class="stats">
    <div class="stat"><div class="stat-l">Episode</div><div class="stat-v cyan" id="s-ep">—</div></div>
    <div class="stat"><div class="stat-l">Step</div><div class="stat-v" id="s-step">0 / 3</div></div>
    <div class="stat"><div class="stat-l">Cumulative Reward</div><div class="stat-v green" id="s-reward">0.000</div></div>
    <div class="stat"><div class="stat-l">Difficulty</div><div class="stat-v" id="s-diff">—</div></div>
    <div class="stat"><div class="stat-l">Status</div><div class="stat-v" id="s-status">Idle</div></div>
  </div>

  <!-- Progress -->
  <div class="progress-wrap">
    <div class="step-dots">
      <div class="step-dot" id="dot-1">E</div>
      <div class="step-dot" id="dot-2">M</div>
      <div class="step-dot" id="dot-3">H</div>
    </div>
    <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
  </div>

  <!-- Main grid -->
  <div class="grid">

    <!-- Email panel -->
    <div class="panel">
      <div class="panel-hdr">
        <span class="panel-title">Incoming Email</span>
        <span class="panel-badge pb-none" id="diff-badge">—</span>
      </div>
      <div class="panel-body" id="email-body">
        <div class="empty">
          <div class="empty-icon">📭</div>
          <div class="empty-text">Start an episode to receive your first email</div>
        </div>
      </div>
    </div>

    <!-- Action panel -->
    <div class="panel">
      <div class="panel-hdr">
        <span class="panel-title">Triage Decision</span>
        <span class="panel-title" style="color:var(--muted)">↓ fill in &amp; submit</span>
      </div>
      <div class="panel-body">

        <!-- Difficulty selector -->
        <div style="margin-bottom:.6rem">
          <div class="field-label">Start at difficulty</div>
          <div class="diff-selector">
            <button class="diff-btn active-easy" id="dbtn-easy"   onclick="selectDiff('easy')">Easy</button>
            <button class="diff-btn"             id="dbtn-medium" onclick="selectDiff('medium')">Medium</button>
            <button class="diff-btn"             id="dbtn-hard"   onclick="selectDiff('hard')">Hard</button>
          </div>
          <div class="diff-note" id="diff-note">Easy → Medium → Hard progression</div>
        </div>

        <div class="field">
          <label class="field-label">Classification</label>
          <select id="f-class">
            <option value="spam">spam</option>
            <option value="urgent">urgent</option>
            <option value="normal" selected>normal</option>
            <option value="newsletter">newsletter</option>
          </select>
        </div>

        <div class="field">
          <label class="field-label">Priority  <span style="font-weight:400;color:var(--muted)">(1 = lowest · 5 = highest)</span></label>
          <input type="number" id="f-priority" min="1" max="5" value="3"/>
        </div>

        <div class="field">
          <label class="field-label">Suggested Reply  <span style="font-weight:400;color:var(--muted)">(or "no_reply")</span></label>
          <textarea id="f-reply" placeholder="no_reply">no_reply</textarea>
        </div>

        <div class="btn-row">
          <button class="btn btn-ghost" id="btn-start" onclick="startEpisode()">Start Episode</button>
          <button class="btn btn-primary" id="btn-submit" onclick="submitStep()" disabled>Submit →</button>
        </div>
      </div>
    </div>

    <!-- Reward panel -->
    <div class="panel">
      <div class="panel-hdr">
        <span class="panel-title">Reward Breakdown</span>
        <span class="panel-title" style="color:var(--muted)">max 1.00</span>
      </div>
      <div class="panel-body" id="reward-body">
        <div class="empty">
          <div class="empty-icon">📊</div>
          <div class="empty-text">Reward appears after each step</div>
        </div>
      </div>
    </div>

    <!-- Episode log -->
    <div class="panel">
      <div class="panel-hdr">
        <span class="panel-title">Episode Log</span>
        <span class="panel-title" id="log-count" style="color:var(--muted)">0 steps</span>
      </div>
      <div class="panel-body" id="log-body">
        <div class="empty">
          <div class="empty-icon">📋</div>
          <div class="empty-text">Steps will appear here</div>
        </div>
      </div>
    </div>

  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let ws = null;
let wsReady = false;
let step = 0;
let cumReward = 0;
let selectedDiff = 'easy';
let currentDiff = 'easy';
const DIFFS = ['easy','medium','hard'];
const DIFF_NOTES = {
  easy:   'Easy → Medium → Hard progression',
  medium: 'Starting at Medium → Hard (2 steps)',
  hard:   'Hard only — maximum challenge (1 step)',
};
let log = [];
let pendingAction = null;

// ── WebSocket ──────────────────────────────────────────────────────────────
const PROTO  = location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = PROTO + '//' + location.host + '/ws';

function setBanner(msg, type) {
  const el = document.getElementById('conn-banner');
  el.textContent = msg;
  el.className = 'conn-banner show ' + type;
}
function hideBanner() {
  document.getElementById('conn-banner').className = 'conn-banner';
}

function setWsTag(state) {
  const el = document.getElementById('ws-tag');
  el.className = 'tag tag-ws';
  if (state === 'connecting') { el.textContent = '⬡ Connecting…'; el.classList.add('connecting'); }
  else if (state === 'open')  { el.textContent = '⬡ Connected'; }
  else                        { el.textContent = '⬡ Disconnected'; el.classList.add('error'); }
}

function connectWS() {
  setWsTag('connecting');
  setBanner('Connecting to environment…', 'connecting');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    wsReady = true;
    setWsTag('open');
    hideBanner();
    document.getElementById('btn-start').disabled = false;
  };

  ws.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }
    handleWsMessage(msg);
  };

  ws.onclose = () => {
    wsReady = false;
    setWsTag('error');
    setBanner('Connection lost. Reconnecting…', 'error');
    document.getElementById('btn-submit').disabled = true;
    setTimeout(connectWS, 2000);
  };

  ws.onerror = () => {
    wsReady = false;
    setWsTag('error');
    setBanner('WebSocket error — retrying…', 'error');
  };
}

function wsSend(obj) {
  if (ws && wsReady) ws.send(JSON.stringify(obj));
}

function handleWsMessage(msg) {
  // WS response types: WSObservationResponse, WSStateResponse, WSErrorResponse
  const data = msg.data || {};

  if (msg.type === 'error') {
    console.error('WS error:', data);
    const errMsg = (data.message || JSON.stringify(data)).slice(0, 120);
    setBanner('Error: ' + errMsg, 'error');
    setTimeout(hideBanner, 4000);
    document.getElementById('btn-submit').disabled = false;
    document.getElementById('btn-submit').textContent = 'Submit →';
    return;
  }

  if (msg.type === 'observation') {
    const obs   = data.observation || data;
    const reward= data.reward ?? obs.reward ?? obs.score ?? 0;
    const done  = data.done ?? obs.done ?? false;

    if (pendingAction === 'reset') {
      pendingAction = null;
      currentDiff = selectedDiff;
      renderEmail(obs, currentDiff);
      setStatus('Active', 'green');
      document.getElementById('btn-submit').disabled = false;
    } else {
      // step response
      step++;
      cumReward += reward;
      const bd = obs.reward_breakdown || null;
      const fb = obs.feedback || '';

      // Advance difficulty display
      const idx = DIFFS.indexOf(currentDiff);
      if (!done && idx < DIFFS.length - 1) currentDiff = DIFFS[idx + 1];

      updateStats();
      updateProgress(done);
      addLogEntry(step, currentDiff, pendingAction, reward);
      renderReward(reward, bd, fb, done);

      if (done) {
        renderDone(cumReward);
        setStatus('Done ✓', 'green');
        document.getElementById('btn-submit').disabled = true;
        document.getElementById('btn-start').textContent = 'New Episode';
      } else {
        renderEmail(obs, currentDiff);
        document.getElementById('btn-submit').disabled = false;
        document.getElementById('btn-submit').textContent = 'Submit →';
      }
      pendingAction = null;
    }
  }
}

// ── Actions ────────────────────────────────────────────────────────────────
function selectDiff(d) {
  selectedDiff = d;
  ['easy','medium','hard'].forEach(x => {
    document.getElementById('dbtn-' + x).className =
      'diff-btn' + (x === d ? ' active-' + d : '');
  });
  document.getElementById('diff-note').textContent = DIFF_NOTES[d];
}

async function startEpisode() {
  if (!wsReady) { setBanner('Not connected yet — please wait', 'connecting'); return; }

  step = 0; cumReward = 0; log = [];
  currentDiff = selectedDiff;

  updateStats();
  updateProgress(false);
  resetDots();
  setStatus('Starting…', 'amber');
  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-submit').disabled = true;
  document.getElementById('email-body').innerHTML = '<div class="empty"><div class="spin"></div><div class="empty-text">Loading email…</div></div>';
  document.getElementById('reward-body').innerHTML = '<div class="empty"><div class="empty-icon">📊</div><div class="empty-text">Reward appears after each step</div></div>';
  document.getElementById('log-body').innerHTML = '<div class="empty"><div class="empty-icon">📋</div><div class="empty-text">Steps will appear here</div></div>';
  document.getElementById('log-count').textContent = '0 steps';

  pendingAction = 'reset';
  wsSend({ type: 'reset', data: { difficulty: selectedDiff } });

  document.getElementById('btn-start').disabled = false;
  document.getElementById('btn-start').textContent = 'Restart';
  document.getElementById('s-ep').textContent = '#' + String(Date.now()).slice(-4);
}

function submitStep() {
  if (!wsReady) { setBanner('Not connected', 'error'); return; }

  const classification   = document.getElementById('f-class').value;
  const priority         = parseInt(document.getElementById('f-priority').value);
  const suggested_reply  = document.getElementById('f-reply').value.trim() || 'no_reply';

  pendingAction = { classification, priority, suggested_reply };

  document.getElementById('btn-submit').disabled = true;
  document.getElementById('btn-submit').innerHTML = '<span class="spin"></span>Grading…';

  wsSend({
    type: 'step',
    data: { classification, priority, suggested_reply },
  });
}

// ── Rendering ──────────────────────────────────────────────────────────────
function renderEmail(obs, diff) {
  const diffMap = { easy:'pb-easy', medium:'pb-medium', hard:'pb-hard' };
  const badge = document.getElementById('diff-badge');
  badge.className = 'panel-badge ' + (diffMap[diff] || 'pb-none');
  badge.textContent = diff || '—';

  const taskDesc = obs.task_description || '';
  let threadHTML = '';
  if (taskDesc.includes('THREAD CONTEXT')) {
    const m = taskDesc.match(/--- THREAD CONTEXT.*?---([\s\S]*?)--- END THREAD/);
    if (m) threadHTML = `
      <div class="thread-ctx">
        <div class="thread-ctx-hdr">🧵 Thread Context</div>
        <div class="thread-ctx-body">${esc(m[1].trim())}</div>
      </div>`;
  }

  document.getElementById('email-body').innerHTML = `
    ${threadHTML}
    <div class="email-meta">FROM</div>
    <div class="email-sender">${esc(obs.sender || '—')}</div>
    <div class="email-meta">SUBJECT</div>
    <div class="email-subject">${esc(obs.email_subject || '—')}</div>
    <div class="email-meta">BODY</div>
    <div class="email-body-wrap">${esc(obs.email_body || '—')}</div>
  `;
}

function renderReward(reward, bd, feedback, done) {
  const col = reward >= 0.8 ? 'var(--green)' : reward >= 0.5 ? 'var(--amber)' : 'var(--red)';

  let bdHTML = '';
  if (bd) {
    const cls  = bd.classification  ?? 0;
    const prio = bd.priority        ?? 0;
    const rep  = bd.reply_quality   ?? 0;
    bdHTML = `
      <div class="bd-row">
        <span class="bd-label">Classification</span>
        <div class="bd-track"><div class="bd-fill" style="width:${cls/0.5*100}%;background:var(--cyan)"></div></div>
        <span class="bd-val" style="color:var(--cyan)">${cls.toFixed(2)}</span>
      </div>
      <div class="bd-row">
        <span class="bd-label">Priority</span>
        <div class="bd-track"><div class="bd-fill" style="width:${prio/0.3*100}%;background:var(--purple)"></div></div>
        <span class="bd-val" style="color:var(--purple)">${prio.toFixed(2)}</span>
      </div>
      <div class="bd-row">
        <span class="bd-label">Reply Quality</span>
        <div class="bd-track"><div class="bd-fill" style="width:${rep/0.2*100}%;background:var(--green)"></div></div>
        <span class="bd-val" style="color:var(--green)">${rep.toFixed(2)}</span>
      </div>`;
  }

  const fbClass = reward >= 0.5 ? 'good' : 'bad';

  // Extract hint if present
  let fbMain = feedback, hint = '';
  const hIdx = feedback.indexOf('| HINT:');
  if (hIdx !== -1) { fbMain = feedback.slice(0, hIdx).trim(); hint = feedback.slice(hIdx + 8).trim(); }

  const hintHTML = hint
    ? `<div class="hint-box"><div class="hint-label">💡 Learning Hint</div>${esc(hint)}</div>`
    : '';

  document.getElementById('reward-body').innerHTML = `
    <div class="score-big" style="color:${col}">${reward.toFixed(2)}</div>
    <div class="score-label">step reward</div>
    ${bdHTML}
    <div class="feedback ${fbClass}">${esc(fbMain)}</div>
    ${hintHTML}
  `;
}

function renderDone(total) {
  const avg = (total / Math.max(step, 1)).toFixed(3);
  const rb  = document.getElementById('reward-body');
  rb.innerHTML = `
    <div class="done-banner">
      <h3>Episode Complete ✓</h3>
      <p>Total Reward: <strong>${total.toFixed(3)}</strong> &nbsp;·&nbsp; Avg: <strong>${avg}</strong></p>
    </div>` + rb.innerHTML;
}

function addLogEntry(stepNum, diff, action, reward) {
  if (!action) return;
  log.push({ stepNum, diff, action, reward });
  document.getElementById('log-count').textContent = log.length + ' step' + (log.length > 1 ? 's' : '');

  const diffColors = { easy:'color:var(--green);background:rgba(34,197,94,.1)', medium:'color:var(--amber);background:rgba(245,158,11,.1)', hard:'color:var(--red);background:rgba(239,68,68,.1)' };
  const sc = reward >= 0.8 ? 'var(--green)' : reward >= 0.5 ? 'var(--amber)' : 'var(--red)';
  const dc = diffColors[diff] || 'color:var(--muted)';

  document.getElementById('log-body').innerHTML = log.map(e => {
    const dcs = diffColors[e.diff] || 'color:var(--muted)';
    const sc2 = e.reward >= 0.8 ? 'var(--green)' : e.reward >= 0.5 ? 'var(--amber)' : 'var(--red)';
    return `<div class="log-row">
      <span class="log-step">${e.stepNum}</span>
      <span class="log-diff"><span style="${dcs};padding:.15rem .45rem;border-radius:3px;font-size:.62rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase">${e.diff}</span></span>
      <span class="log-action">${esc(e.action.classification)} · p${e.action.priority}</span>
      <span class="log-score" style="color:${sc2}">${e.reward.toFixed(3)}</span>
    </div>`;
  }).join('');
}

function updateStats() {
  document.getElementById('s-step').textContent   = step + ' / 3';
  document.getElementById('s-reward').textContent = cumReward.toFixed(3);
  document.getElementById('s-diff').textContent   = currentDiff || '—';
}

function updateProgress(done) {
  const pct = done ? 100 : (step / 3) * 100;
  document.getElementById('progress-fill').style.width = pct + '%';
  DIFFS.forEach((d, i) => {
    const dot = document.getElementById('dot-' + (i + 1));
    if (i < step) dot.className = 'step-dot done';
    else if (i === step && !done) dot.className = 'step-dot active';
    else dot.className = 'step-dot';
  });
}

function resetDots() {
  DIFFS.forEach((_, i) => document.getElementById('dot-' + (i + 1)).className = 'step-dot');
  document.getElementById('progress-fill').style.width = '0%';
}

function setStatus(text, color) {
  const el = document.getElementById('s-status');
  el.textContent = text;
  el.className = 'stat-v ' + color;
}

function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/\n/g,'<br>');
}

// ── Boot ───────────────────────────────────────────────────────────────────
document.getElementById('btn-start').disabled = true;
document.getElementById('btn-submit').disabled = true;
connectWS();
</script>
</body>
</html>
"""


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