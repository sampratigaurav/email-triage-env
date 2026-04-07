import sys
import os
import random
import uuid
import asyncio
from typing import Dict, Optional

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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

app = create_app(
    EmailTriageEnvironment,
    EmailTriageAction,
    EmailTriageObservation,
    env_name="email_triage_env",
    max_concurrent_envs=10,
)

# ── Server-side session store for the demo UI ─────────────────────────────────
# Keeps one EmailTriageEnvironment instance per browser session so state
# persists across reset → step → step → step HTTP calls.
_sessions: Dict[str, EmailTriageEnvironment] = {}

def _get_or_create(session_id: str) -> EmailTriageEnvironment:
    if session_id not in _sessions:
        _sessions[session_id] = EmailTriageEnvironment()
    # Evict old sessions if too many (keep last 50)
    if len(_sessions) > 50:
        oldest = next(iter(_sessions))
        del _sessions[oldest]
    return _sessions[session_id]

# ── Demo API endpoints ────────────────────────────────────────────────────────

class DemoResetRequest(BaseModel):
    session_id: str
    difficulty: str = "easy"

class DemoStepRequest(BaseModel):
    session_id: str
    classification: str
    priority: int
    suggested_reply: str

def obs_to_dict(obs: EmailTriageObservation, env: EmailTriageEnvironment) -> dict:
    return {
        "email_subject":    obs.email_subject,
        "email_body":       obs.email_body,
        "sender":           obs.sender,
        "task_description": obs.task_description,
        "feedback":         obs.feedback,
        "score":            obs.score,
        "reward":           obs.reward,
        "done":             obs.done,
        "reward_breakdown": obs.reward_breakdown,
        "difficulty":       env._difficulty,
    }

@app.post("/demo/reset")
def demo_reset(req: DemoResetRequest):
    env = _get_or_create(req.session_id)
    obs = env.reset(difficulty=req.difficulty)
    return JSONResponse(obs_to_dict(obs, env))

@app.post("/demo/step")
def demo_step(req: DemoStepRequest):
    if req.session_id not in _sessions:
        return JSONResponse({"error": "Session not found. Please reset first."}, status_code=400)
    env = _sessions[req.session_id]
    action = EmailTriageAction(
        classification=req.classification,
        priority=req.priority,
        suggested_reply=req.suggested_reply,
    )
    obs = env.step(action)
    return JSONResponse(obs_to_dict(obs, env))

# ── /benchmark endpoint ────────────────────────────────────────────────────────

@app.get("/benchmark")
def benchmark():
    random.seed(42)
    env = EmailTriageEnvironment()
    results = {}
    total_tasks = 0
    total_oracle = 0.0

    for difficulty, task_list in TASKS.items():
        diff_results = []
        for task in task_list:
            total_tasks += 1
            oracle_action = EmailTriageAction(
                classification=task["correct_classification"],
                priority=task["correct_priority"],
                suggested_reply=(
                    " ".join(task.get("required_reply_keywords", []))
                    + " I authorize this action and confirm the request."
                    if task.get("needs_reply") else "no_reply"
                ),
            )
            oracle_score, oracle_bd = env._grade_action(oracle_action, task)
            naive_action = EmailTriageAction(classification="normal", priority=3, suggested_reply="no_reply")
            naive_score, naive_bd = env._grade_action(naive_action, task)
            total_oracle += oracle_score
            diff_results.append({
                "email_subject":          task["email_subject"],
                "sender":                 task["sender"],
                "correct_classification": task["correct_classification"],
                "correct_priority":       task["correct_priority"],
                "adversarial":            task.get("adversarial", False),
                "has_thread_context":     bool(task.get("thread_context")),
                "oracle_score":           oracle_score,
                "oracle_breakdown":       oracle_bd,
                "naive_score":            naive_score,
                "naive_breakdown":        naive_bd,
                "improvement_headroom":   round(oracle_score - naive_score, 2),
            })
        results[difficulty] = {
            "tasks":            diff_results,
            "avg_oracle_score": round(sum(t["oracle_score"] for t in diff_results) / len(diff_results), 3),
            "avg_naive_score":  round(sum(t["naive_score"]  for t in diff_results) / len(diff_results), 3),
        }

    return JSONResponse({
        "benchmark":          "email_triage_env",
        "version":            "2.0.0",
        "seed":               42,
        "total_tasks":        total_tasks,
        "overall_oracle_avg": round(total_oracle / total_tasks, 3),
        "summary": {
            diff: {
                "avg_oracle": results[diff]["avg_oracle_score"],
                "avg_naive":  results[diff]["avg_naive_score"],
                "task_count": len(results[diff]["tasks"]),
            } for diff in results
        },
        "details": results,
        "note": "oracle = perfect agent. naive = always normal/3/no_reply.",
    })

# ── /info endpoint ─────────────────────────────────────────────────────────────

@app.get("/info")
def info():
    return JSONResponse({
        "name": "email_triage_env", "version": "2.0.0",
        "difficulty_levels": ["easy", "medium", "hard"],
        "episode_steps": 3, "reward_range": [0.0, 1.0],
        "reward_components": {"classification": "0.0–0.50", "priority": "0.0–0.30", "reply_quality": "0.0–0.20"},
        "action_space": {"classification": "spam|urgent|normal|newsletter", "priority": "1-5", "suggested_reply": "str"},
        "special_features": ["Adversarial emails (4 types)", "Thread context", "reward_breakdown", "Partial credit"],
        "endpoints": {"/": "Demo UI", "/demo/reset": "POST", "/demo/step": "POST",
                      "/reset": "POST OpenEnv", "/step": "POST OpenEnv",
                      "/benchmark": "GET", "/tasks": "GET", "/info": "GET", "/health": "GET"},
    })

# ── /tasks endpoint ────────────────────────────────────────────────────────────

@app.get("/tasks")
def list_tasks():
    summary = {}
    for difficulty, task_list in TASKS.items():
        summary[difficulty] = [{
            "email_subject": t["email_subject"], "sender": t["sender"],
            "correct_classification": t["correct_classification"],
            "correct_priority": t["correct_priority"],
            "needs_reply": t.get("needs_reply", False),
            "adversarial": t.get("adversarial", False),
            "has_thread_context": bool(t.get("thread_context")),
        } for t in task_list]
    return JSONResponse({"total_tasks": sum(len(v) for v in TASKS.values()), "tasks_by_difficulty": summary})

# ── Demo UI ────────────────────────────────────────────────────────────────────

DEMO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Email Triage Environment</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@600;800&display=swap" rel="stylesheet"/>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#070b11;--panel:#0d1520;--panel2:#111d2e;
  --border:#1a2c42;--border2:#243d57;
  --blue:#3b82f6;--cyan:#06b6d4;--green:#22c55e;
  --amber:#f59e0b;--red:#ef4444;--purple:#8b5cf6;
  --text:#f1f5f9;--muted:#475569;--muted2:#64748b;
  --mono:'JetBrains Mono',monospace;--display:'Syne',sans-serif;
}
body{background:var(--bg);color:var(--text);font-family:var(--mono);min-height:100vh;overflow-x:hidden}
body::after{content:'';position:fixed;inset:0;background-image:radial-gradient(circle,#1e3a5f22 1px,transparent 1px);background-size:32px 32px;pointer-events:none;z-index:0}
.wrap{position:relative;z-index:1;max-width:1200px;margin:0 auto;padding:1.5rem 1.5rem 4rem}

/* header */
.hdr{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1.5rem;padding-bottom:1.25rem;border-bottom:1px solid var(--border);flex-wrap:wrap}
.hdr-left h1{font-family:var(--display);font-size:1.5rem;font-weight:800;letter-spacing:-.03em;background:linear-gradient(135deg,var(--cyan),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hdr-left p{font-size:.68rem;color:var(--muted2);margin-top:.25rem;letter-spacing:.05em}
.tags{display:flex;gap:.4rem;margin-top:.5rem;flex-wrap:wrap}
.tag{font-size:.6rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:.2rem .55rem;border-radius:3px}
.tag-live{background:rgba(34,197,94,.12);color:var(--green);border:1px solid rgba(34,197,94,.3)}
.tag-oe{background:rgba(59,130,246,.1);color:var(--blue);border:1px solid rgba(59,130,246,.25)}
.hdr-links{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
.hdr-link{font-size:.68rem;color:var(--muted2);text-decoration:none;padding:.28rem .6rem;border:1px solid var(--border);border-radius:4px;transition:all .15s}
.hdr-link:hover{color:var(--cyan);border-color:var(--cyan)}

/* stats */
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--border);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:1.25rem}
.stat{background:var(--panel);padding:.75rem 1rem}
.stat-l{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.25rem}
.stat-v{font-size:1.1rem;font-weight:700}
.c-cyan{color:var(--cyan)}.c-green{color:var(--green)}.c-amber{color:var(--amber)}.c-red{color:var(--red)}.c-text{color:var(--text)}

/* progress */
.prog-row{display:flex;align-items:center;gap:.85rem;margin-bottom:1.25rem}
.step-dots{display:flex;gap:.4rem}
.dot{width:26px;height:26px;border-radius:50%;border:2px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:.58rem;font-weight:700;color:var(--muted);transition:all .2s}
.dot.done{border-color:var(--green);color:var(--green);background:rgba(34,197,94,.1)}
.dot.active{border-color:var(--cyan);color:var(--cyan);background:rgba(6,182,212,.1)}
.prog-track{flex:1;height:4px;background:var(--border);border-radius:2px;overflow:hidden}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .4s ease;width:0%}

/* grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:.85rem}
@media(max-width:720px){.grid{grid-template-columns:1fr}}

/* panel */
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;overflow:hidden;animation:fadeUp .3s ease both}
.panel:nth-child(2){animation-delay:.05s}.panel:nth-child(3){animation-delay:.1s}.panel:nth-child(4){animation-delay:.15s}
.ph{display:flex;align-items:center;justify-content:space-between;padding:.6rem 1rem;border-bottom:1px solid var(--border);background:var(--panel2)}
.ph-title{font-size:.62rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--muted2)}
.ph-badge{font-size:.58rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:.18rem .5rem;border-radius:3px}
.pb-easy{background:rgba(34,197,94,.12);color:var(--green)}
.pb-medium{background:rgba(245,158,11,.12);color:var(--amber)}
.pb-hard{background:rgba(239,68,68,.12);color:var(--red)}
.pb-none{background:rgba(71,85,105,.1);color:var(--muted)}
.pb{padding:1rem}

/* email */
.e-label{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.2rem}
.e-sender{font-size:.78rem;color:var(--muted2);margin-bottom:.65rem;padding-bottom:.65rem;border-bottom:1px solid var(--border)}
.e-subject{font-family:var(--display);font-size:1rem;font-weight:600;color:var(--text);margin-bottom:.75rem;line-height:1.3}
.e-body{background:var(--panel2);border:1px solid var(--border);border-radius:5px;padding:.75rem;font-size:.78rem;line-height:1.7;color:#94a3b8;max-height:140px;overflow-y:auto}
.thread-box{margin-bottom:.75rem;background:rgba(139,92,246,.06);border:1px solid rgba(139,92,246,.2);border-radius:5px;padding:.65rem}
.thread-lbl{font-size:.58rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--purple);margin-bottom:.35rem}
.thread-txt{font-size:.72rem;color:#a78bfa;line-height:1.6}

/* form */
.diff-row{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-bottom:.5rem}
.dbtn{padding:.45rem;border-radius:5px;border:1px solid var(--border);background:transparent;color:var(--muted2);font-family:var(--mono);font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;transition:all .15s;text-align:center;width:100%}
.dbtn:hover{border-color:var(--border2);color:var(--text)}
.dbtn.sel-easy{background:rgba(34,197,94,.12);border-color:var(--green);color:var(--green)}
.dbtn.sel-medium{background:rgba(245,158,11,.12);border-color:var(--amber);color:var(--amber)}
.dbtn.sel-hard{background:rgba(239,68,68,.12);border-color:var(--red);color:var(--red)}
.diff-note{font-size:.62rem;color:var(--muted);margin-bottom:.85rem;text-align:center}
.field{margin-bottom:.75rem}
.fl{display:block;font-size:.6rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:.3rem}
select,input[type=number],textarea{width:100%;background:var(--panel2);border:1px solid var(--border);border-radius:5px;color:var(--text);font-family:var(--mono);font-size:.8rem;padding:.5rem .7rem;outline:none;transition:border-color .15s,box-shadow .15s;appearance:none;-webkit-appearance:none}
select:focus,input:focus,textarea:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(59,130,246,.12)}
textarea{resize:vertical;min-height:60px}
.btn-row{display:flex;gap:.6rem;margin-top:.85rem}
.btn{flex:1;padding:.65rem;border-radius:6px;border:none;font-family:var(--mono);font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;transition:all .15s}
.btn:disabled{opacity:.35;cursor:not-allowed}
.btn-p{background:linear-gradient(135deg,var(--blue),var(--cyan));color:#fff}
.btn-p:hover:not(:disabled){opacity:.88;transform:translateY(-1px)}
.btn-g{background:transparent;color:var(--muted2);border:1px solid var(--border)}
.btn-g:hover:not(:disabled){border-color:var(--border2);color:var(--text)}

/* reward */
.score-big{font-family:var(--display);font-size:2.6rem;font-weight:800;text-align:center;line-height:1;margin-bottom:.15rem}
.score-lbl{font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);text-align:center;margin-bottom:1.1rem}
.bd-row{display:flex;align-items:center;gap:.65rem;margin-bottom:.55rem}
.bd-lbl{font-size:.62rem;color:var(--muted2);width:95px;flex-shrink:0}
.bd-track{flex:1;height:5px;background:var(--border);border-radius:3px;overflow:hidden}
.bd-fill{height:100%;border-radius:3px;transition:width .5s cubic-bezier(.4,0,.2,1);width:0%}
.bd-val{font-size:.68rem;font-weight:700;width:30px;text-align:right;flex-shrink:0}
.feedback{margin-top:.85rem;padding:.65rem .85rem;border-radius:5px;font-size:.72rem;line-height:1.6;color:#94a3b8;background:var(--panel2);border:1px solid var(--border);border-left:3px solid var(--border2);word-break:break-word}
.feedback.good{border-left-color:var(--green)}.feedback.bad{border-left-color:var(--red)}
.hint-box{margin-top:.75rem;padding:.6rem .8rem;border-radius:5px;font-size:.7rem;line-height:1.6;background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.2);color:#fbbf24}
.hint-lbl{font-size:.58rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:.25rem;color:var(--amber)}

/* log */
.log-row{display:grid;grid-template-columns:24px 72px 1fr 52px;gap:.4rem;align-items:center;padding:.5rem 0;border-bottom:1px solid var(--border);font-size:.7rem}
.log-row:last-child{border-bottom:none}
.log-step{color:var(--muted);text-align:center}
.log-action{color:#94a3b8}
.log-score{font-weight:700;text-align:right}

/* done */
.done-banner{background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.25);border-radius:8px;padding:1.1rem;text-align:center;margin-bottom:.85rem}
.done-banner h3{font-family:var(--display);font-size:1.2rem;font-weight:800;color:var(--green);margin-bottom:.2rem}
.done-banner p{font-size:.72rem;color:var(--muted2)}

/* error toast */
.toast{position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:var(--red);font-size:.72rem;padding:.6rem 1.2rem;border-radius:6px;z-index:999;display:none;max-width:480px;text-align:center}
.toast.show{display:block}

/* empty */
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem 1rem;color:var(--muted);gap:.4rem}
.empty-icon{font-size:1.8rem}
.empty-text{font-size:.72rem;text-align:center}

/* spinner */
.spin{display:inline-block;width:11px;height:11px;border:2px solid transparent;border-top-color:currentColor;border-radius:50%;animation:rot .6s linear infinite;vertical-align:middle;margin-right:.3rem}
@keyframes rot{to{transform:rotate(360deg)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:2px}
</style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div class="hdr">
    <div class="hdr-left">
      <h1>📬 email_triage_env</h1>
      <p>REAL-WORLD RL ENVIRONMENT · META PYTORCH × SCALER HACKATHON 2026</p>
      <div class="tags">
        <span class="tag tag-live">● Live</span>
        <span class="tag tag-oe">OpenEnv v1</span>
      </div>
    </div>
    <div class="hdr-links">
      <a class="hdr-link" href="/docs" target="_blank">API Docs</a>
      <a class="hdr-link" href="/benchmark" target="_blank">Benchmark</a>
      <a class="hdr-link" href="/tasks" target="_blank">All Tasks</a>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat"><div class="stat-l">Episode</div><div class="stat-v c-cyan" id="s-ep">—</div></div>
    <div class="stat"><div class="stat-l">Step</div><div class="stat-v c-text" id="s-step">0 / 3</div></div>
    <div class="stat"><div class="stat-l">Cumulative Reward</div><div class="stat-v c-green" id="s-reward">0.000</div></div>
    <div class="stat"><div class="stat-l">Difficulty</div><div class="stat-v c-text" id="s-diff">—</div></div>
    <div class="stat"><div class="stat-l">Status</div><div class="stat-v c-text" id="s-status">Idle</div></div>
  </div>

  <!-- Progress -->
  <div class="prog-row">
    <div class="step-dots">
      <div class="dot" id="dot-1">E</div>
      <div class="dot" id="dot-2">M</div>
      <div class="dot" id="dot-3">H</div>
    </div>
    <div class="prog-track"><div class="prog-fill" id="prog-fill"></div></div>
  </div>

  <!-- Grid -->
  <div class="grid">

    <!-- Email -->
    <div class="panel">
      <div class="ph">
        <span class="ph-title">Incoming Email</span>
        <span class="ph-badge pb-none" id="diff-badge">—</span>
      </div>
      <div class="pb" id="email-panel">
        <div class="empty"><div class="empty-icon">📭</div><div class="empty-text">Start an episode to receive your first email</div></div>
      </div>
    </div>

    <!-- Action -->
    <div class="panel">
      <div class="ph">
        <span class="ph-title">Triage Decision</span>
        <span class="ph-title" style="color:var(--muted)">fill in &amp; submit</span>
      </div>
      <div class="pb">
        <div class="field">
          <div class="fl">Start at difficulty</div>
          <div class="diff-row">
            <button class="dbtn sel-easy" id="dbtn-easy"   onclick="selDiff('easy')">Easy</button>
            <button class="dbtn"          id="dbtn-medium" onclick="selDiff('medium')">Medium</button>
            <button class="dbtn"          id="dbtn-hard"   onclick="selDiff('hard')">Hard</button>
          </div>
          <div class="diff-note" id="diff-note">Easy → Medium → Hard progression</div>
        </div>

        <div class="field">
          <label class="fl" for="f-class">Classification</label>
          <select id="f-class">
            <option value="spam">spam</option>
            <option value="urgent">urgent</option>
            <option value="normal" selected>normal</option>
            <option value="newsletter">newsletter</option>
          </select>
        </div>

        <div class="field">
          <label class="fl" for="f-priority">Priority <span style="font-weight:400;color:var(--muted)">(1 = lowest · 5 = highest)</span></label>
          <input type="number" id="f-priority" min="1" max="5" value="3"/>
        </div>

        <div class="field">
          <label class="fl" for="f-reply">Suggested Reply <span style="font-weight:400;color:var(--muted)">(or "no_reply")</span></label>
          <textarea id="f-reply" placeholder="no_reply">no_reply</textarea>
        </div>

        <div class="btn-row">
          <button class="btn btn-g" id="btn-start" onclick="startEpisode()">▶ Start Episode</button>
          <button class="btn btn-p" id="btn-submit" onclick="doStep()" disabled>Submit →</button>
        </div>
      </div>
    </div>

    <!-- Reward -->
    <div class="panel">
      <div class="ph">
        <span class="ph-title">Reward Breakdown</span>
        <span class="ph-title" style="color:var(--muted)">max 1.00</span>
      </div>
      <div class="pb" id="reward-panel">
        <div class="empty"><div class="empty-icon">📊</div><div class="empty-text">Reward appears after each step</div></div>
      </div>
    </div>

    <!-- Log -->
    <div class="panel">
      <div class="ph">
        <span class="ph-title">Episode Log</span>
        <span class="ph-title c-muted" id="log-count" style="color:var(--muted)">0 steps</span>
      </div>
      <div class="pb" id="log-panel">
        <div class="empty"><div class="empty-icon">📋</div><div class="empty-text">Steps will appear here</div></div>
      </div>
    </div>

  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let sessionId = 'demo-' + Math.random().toString(36).slice(2, 10);
let selDiffVal = 'easy';
let curDiff    = 'easy';
let stepNum    = 0;
let cumReward  = 0;
let logEntries = [];
const DIFFS    = ['easy','medium','hard'];
const NOTES    = {
  easy:   'Easy → Medium → Hard  (3 steps)',
  medium: 'Medium → Hard  (2 steps)',
  hard:   'Hard only  (1 step)',
};

// ── Difficulty selector ─────────────────────────────────────────────────────
function selDiff(d) {
  selDiffVal = d;
  DIFFS.forEach(function(x) {
    var btn = document.getElementById('dbtn-' + x);
    btn.className = 'dbtn' + (x === d ? ' sel-' + d : '');
  });
  document.getElementById('diff-note').textContent = NOTES[d];
}

// ── API helpers ─────────────────────────────────────────────────────────────
async function apiPost(path, body) {
  var res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    var txt = await res.text();
    throw new Error('HTTP ' + res.status + ': ' + txt.slice(0, 120));
  }
  return res.json();
}

// ── Start episode ──────────────────────────────────────────────────────────
async function startEpisode() {
  stepNum = 0; cumReward = 0; logEntries = [];
  curDiff = selDiffVal;

  setStatus('Starting…', 'c-amber');
  setBusy(true);
  resetProgress();

  document.getElementById('email-panel').innerHTML  = '<div class="empty"><div class="spin"></div><div class="empty-text">Loading email…</div></div>';
  document.getElementById('reward-panel').innerHTML = '<div class="empty"><div class="empty-icon">📊</div><div class="empty-text">Reward appears after each step</div></div>';
  document.getElementById('log-panel').innerHTML    = '<div class="empty"><div class="empty-icon">📋</div><div class="empty-text">Steps will appear here</div></div>';
  document.getElementById('log-count').textContent  = '0 steps';
  document.getElementById('s-ep').textContent = '#' + sessionId.slice(-4);
  document.getElementById('s-step').textContent   = '0 / 3';
  document.getElementById('s-reward').textContent = '0.000';
  document.getElementById('s-diff').textContent   = curDiff;

  try {
    var obs = await apiPost('/demo/reset', {session_id: sessionId, difficulty: selDiffVal});
    renderEmail(obs);
    setStatus('Active', 'c-green');
    document.getElementById('btn-submit').disabled = false;
    document.getElementById('btn-start').textContent = '↺ Restart';
  } catch(e) {
    showToast('Reset failed: ' + e.message);
    setStatus('Error', 'c-red');
  }
  setBusy(false);
}

// ── Submit step ─────────────────────────────────────────────────────────────
async function doStep() {
  var cls    = document.getElementById('f-class').value;
  var pri    = parseInt(document.getElementById('f-priority').value) || 3;
  var reply  = document.getElementById('f-reply').value.trim() || 'no_reply';

  document.getElementById('btn-submit').disabled = true;
  document.getElementById('btn-submit').innerHTML = '<span class="spin"></span>Grading…';

  try {
    var obs = await apiPost('/demo/step', {
      session_id: sessionId,
      classification: cls,
      priority: pri,
      suggested_reply: reply,
    });

    stepNum++;
    cumReward += (obs.reward || obs.score || 0);

    // Update stats
    document.getElementById('s-step').textContent   = stepNum + ' / 3';
    document.getElementById('s-reward').textContent = cumReward.toFixed(3);
    document.getElementById('s-diff').textContent   = obs.difficulty || curDiff;

    // Advance local diff tracker
    var idx = DIFFS.indexOf(curDiff);
    if (!obs.done && idx < DIFFS.length - 1) curDiff = DIFFS[idx + 1];

    updateProgress(obs.done);
    addLog(stepNum, obs.difficulty || DIFFS[Math.min(idx, 2)], cls, pri, obs.reward || obs.score || 0);
    renderReward(obs);

    if (obs.done) {
      renderDone(cumReward);
      setStatus('Done ✓', 'c-green');
      document.getElementById('btn-submit').disabled = true;
      document.getElementById('btn-submit').textContent = 'Submit →';
      document.getElementById('btn-start').textContent = '▶ New Episode';
    } else {
      renderEmail(obs);
      document.getElementById('btn-submit').disabled = false;
      document.getElementById('btn-submit').textContent = 'Submit →';
    }
  } catch(e) {
    showToast('Step failed: ' + e.message);
    document.getElementById('btn-submit').disabled = false;
    document.getElementById('btn-submit').textContent = 'Submit →';
  }
}

// ── Render helpers ──────────────────────────────────────────────────────────
function renderEmail(obs) {
  var diff = obs.difficulty || curDiff;
  var badge = document.getElementById('diff-badge');
  badge.className = 'ph-badge pb-' + (diff || 'none');
  badge.textContent = diff || '—';

  var threadHTML = '';
  var td = obs.task_description || '';
  if (td.indexOf('THREAD CONTEXT') !== -1) {
    var m = td.match(/--- THREAD CONTEXT.*?---([\s\S]*?)--- END THREAD/);
    if (m) threadHTML = '<div class="thread-box"><div class="thread-lbl">🧵 Thread Context</div><div class="thread-txt">' + esc(m[1].trim()) + '</div></div>';
  }

  document.getElementById('email-panel').innerHTML =
    threadHTML +
    '<div class="e-label">FROM</div>' +
    '<div class="e-sender">' + esc(obs.sender || '—') + '</div>' +
    '<div class="e-label">SUBJECT</div>' +
    '<div class="e-subject">' + esc(obs.email_subject || '—') + '</div>' +
    '<div class="e-label">BODY</div>' +
    '<div class="e-body">' + esc(obs.email_body || '—') + '</div>';
}

function renderReward(obs) {
  var reward = obs.reward || obs.score || 0;
  var col = reward >= 0.8 ? 'var(--green)' : reward >= 0.5 ? 'var(--amber)' : 'var(--red)';
  var bd  = obs.reward_breakdown || {};
  var cls = bd.classification || 0;
  var pri = bd.priority       || 0;
  var rep = bd.reply_quality  || 0;

  var bdHTML = '<div class="bd-row"><span class="bd-lbl">Classification</span><div class="bd-track"><div class="bd-fill" style="width:' + (cls/0.5*100) + '%;background:var(--cyan)"></div></div><span class="bd-val" style="color:var(--cyan)">' + cls.toFixed(2) + '</span></div>' +
    '<div class="bd-row"><span class="bd-lbl">Priority</span><div class="bd-track"><div class="bd-fill" style="width:' + (pri/0.3*100) + '%;background:var(--purple)"></div></div><span class="bd-val" style="color:var(--purple)">' + pri.toFixed(2) + '</span></div>' +
    '<div class="bd-row"><span class="bd-lbl">Reply Quality</span><div class="bd-track"><div class="bd-fill" style="width:' + (rep/0.2*100) + '%;background:var(--green)"></div></div><span class="bd-val" style="color:var(--green)">' + rep.toFixed(2) + '</span></div>';

  var fb = obs.feedback || '';
  var hint = '';
  var hIdx = fb.indexOf('| HINT:');
  if (hIdx !== -1) { hint = fb.slice(hIdx + 8).trim(); fb = fb.slice(0, hIdx).trim(); }

  var fbClass = reward >= 0.5 ? 'good' : 'bad';
  var hintHTML = hint ? '<div class="hint-box"><div class="hint-lbl">💡 Learning Hint</div>' + esc(hint) + '</div>' : '';

  document.getElementById('reward-panel').innerHTML =
    '<div class="score-big" style="color:' + col + '">' + reward.toFixed(2) + '</div>' +
    '<div class="score-lbl">step reward</div>' +
    bdHTML +
    '<div class="feedback ' + fbClass + '">' + esc(fb) + '</div>' +
    hintHTML;
}

function renderDone(total) {
  var avg = (total / Math.max(stepNum, 1)).toFixed(3);
  var rp = document.getElementById('reward-panel');
  rp.innerHTML = '<div class="done-banner"><h3>Episode Complete ✓</h3><p>Total: <strong>' + total.toFixed(3) + '</strong> · Avg: <strong>' + avg + '</strong></p></div>' + rp.innerHTML;
}

function addLog(sn, diff, cls, pri, reward) {
  logEntries.push({sn, diff, cls, pri, reward});
  document.getElementById('log-count').textContent = logEntries.length + ' step' + (logEntries.length !== 1 ? 's' : '');
  var dColors = {easy:'color:var(--green);background:rgba(34,197,94,.1)', medium:'color:var(--amber);background:rgba(245,158,11,.1)', hard:'color:var(--red);background:rgba(239,68,68,.1)'};
  document.getElementById('log-panel').innerHTML = logEntries.map(function(e) {
    var sc = e.reward >= 0.8 ? 'var(--green)' : e.reward >= 0.5 ? 'var(--amber)' : 'var(--red)';
    var dc = dColors[e.diff] || 'color:var(--muted)';
    return '<div class="log-row">' +
      '<span class="log-step">' + e.sn + '</span>' +
      '<span style="' + dc + ';padding:.12rem .4rem;border-radius:3px;font-size:.6rem;font-weight:700;text-transform:uppercase">' + (e.diff||'?') + '</span>' +
      '<span class="log-action">' + esc(e.cls) + ' · p' + e.pri + '</span>' +
      '<span class="log-score" style="color:' + sc + '">' + e.reward.toFixed(3) + '</span>' +
    '</div>';
  }).join('');
}

// ── UI helpers ──────────────────────────────────────────────────────────────
function setStatus(t, c) {
  var el = document.getElementById('s-status');
  el.textContent = t;
  el.className = 'stat-v ' + c;
}

function setBusy(b) {
  document.getElementById('btn-start').disabled = b;
}

function updateProgress(done) {
  var pct = done ? 100 : (stepNum / 3 * 100);
  document.getElementById('prog-fill').style.width = pct + '%';
  DIFFS.forEach(function(d, i) {
    var dot = document.getElementById('dot-' + (i + 1));
    if (i < stepNum) dot.className = 'dot done';
    else if (i === stepNum && !done) dot.className = 'dot active';
    else dot.className = 'dot';
  });
}

function resetProgress() {
  document.getElementById('prog-fill').style.width = '0%';
  DIFFS.forEach(function(_, i) { document.getElementById('dot-' + (i + 1)).className = 'dot'; });
}

function showToast(msg) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show';
  setTimeout(function() { t.className = 'toast'; }, 5000);
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def demo_ui():
    """Live interactive demo UI."""
    return DEMO_HTML


# ── Server entry point ─────────────────────────────────────────────────────────

def main(host: str = "0.0.0.0", port: int = 7860):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()  # noqa: required by openenv validate