import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError(
        "openenv is required. Install with: pip install openenv-core"
    ) from e

try:
    from ..models import EmailTriageAction, EmailTriageObservation
    from .email_triage_env_environment import EmailTriageEnvironment, TASKS
except (ModuleNotFoundError, ImportError):
    from models import EmailTriageAction, EmailTriageObservation
    from server.email_triage_env_environment import EmailTriageEnvironment, TASKS

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = create_app(
    EmailTriageEnvironment,
    EmailTriageAction,
    EmailTriageObservation,
    env_name="email_triage_env",
    max_concurrent_envs=1,
)


# ── Extra endpoints for judges and validators ─────────────────────────────────

@app.get("/info")
def info():
    """Environment metadata — useful for openenv validate and judge inspection."""
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
            "Adversarial emails (4 types: spam-framed urgent, urgent-framed newsletter, "
            "polite-framed critical, CEO fraud BEC attack)",
            "Thread context injection for multi-turn reasoning",
            "Granular reward_breakdown per step",
            "Partial credit grading (no binary 0/1 rewards)",
        ],
    })


@app.get("/tasks")
def list_tasks():
    """Return all tasks grouped by difficulty — for judge inspection."""
    summary = {}
    for difficulty, task_list in TASKS.items():
        summary[difficulty] = [
            {
                "email_subject":          t["email_subject"],
                "sender":                 t["sender"],
                "correct_classification": t["correct_classification"],
                "correct_priority":       t["correct_priority"],
                "needs_reply":            t.get("needs_reply", False),
                "adversarial":            t.get("adversarial", False),
                "has_thread_context":     bool(t.get("thread_context")),
                "required_reply_keywords": t.get("required_reply_keywords", []),
            }
            for t in task_list
        ]
    return JSONResponse({
        "total_tasks": sum(len(v) for v in TASKS.values()),
        "tasks_by_difficulty": summary,
    })


# ── Server entry point ────────────────────────────────────────────────────────

def main(host: str = "0.0.0.0", port: int = 7860):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    main(port=args.port)