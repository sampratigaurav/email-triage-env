"""
Inference script for Email Triage Environment.
Judges run this file to evaluate the submission.
Logs output in the required [START] / [STEP] / [END] format.
"""

import os
import json
import time
import asyncio

from openai import OpenAI

# ── Configuration ─────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN",     "")
ENV_URL      = os.environ.get("ENV_URL",      "http://localhost:8000")

llm = OpenAI(
    api_key=HF_TOKEN if HF_TOKEN else "dummy-key",
    base_url=API_BASE_URL,
)


# ── LLM agent ────────────────────────────────────────────────────────────────
def ask_llm(email_subject: str, email_body: str, sender: str, task_desc: str) -> dict:
    """Send the email to the LLM and get back a triage decision as JSON."""

    prompt = f"""You are an expert email triage assistant working in a professional office.

Task: {task_desc}

Email to triage:
From: {sender}
Subject: {email_subject}

Body:
{email_body}

You must respond with ONLY a valid JSON object — no explanation, no markdown, no code fences.
Use exactly this structure:

{{
  "classification": "spam",
  "priority": 1,
  "suggested_reply": "no_reply"
}}

Rules:
- classification must be one of: spam, urgent, normal, newsletter
- priority must be an integer from 1 (lowest) to 5 (highest)
- suggested_reply must be a short reply string, or exactly "no_reply" if no reply is needed
"""

    response = llm.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model adds them anyway
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()

    return json.loads(raw)


# ── Fallback if LLM fails ────────────────────────────────────────────────────
def safe_ask_llm(email_subject: str, email_body: str, sender: str, task_desc: str) -> dict:
    """Wrap ask_llm with a fallback so the script never crashes."""
    try:
        return ask_llm(email_subject, email_body, sender, task_desc)
    except Exception as e:
        print(json.dumps({"event": "[WARN]", "message": f"LLM call failed: {str(e)}, using fallback"}))
        return {
            "classification": "normal",
            "priority": 3,
            "suggested_reply": "Thank you for your email. I will review this shortly.",
        }


# ── Main episode loop ─────────────────────────────────────────────────────────
async def run_episode():
    from email_triage_env.client import EmailTriageEnv
    from email_triage_env.models import EmailTriageAction

    # [START] log — required by judges
    print(json.dumps({
        "event":     "[START]",
        "env":       "email_triage_env",
        "model":     MODEL_NAME,
        "timestamp": time.time(),
    }), flush=True)

    total_reward = 0.0
    step = 0

    async with EmailTriageEnv(base_url=ENV_URL) as env:

        # Reset the environment — get first email
        result = await env.reset()

        while True:
            obs = result.observation

            # Agent decides what to do
            action_dict = safe_ask_llm(
                email_subject=obs.email_subject,
                email_body=obs.email_body,
                sender=obs.sender,
                task_desc=obs.task_description,
            )

            # Send action to environment
            action = EmailTriageAction(**action_dict)
            result = await env.step(action)

            step += 1
            reward = result.reward if result.reward is not None else 0.0
            total_reward += reward

            # [STEP] log — required by judges
            print(json.dumps({
                "event":    "[STEP]",
                "step":     step,
                "action":   action_dict,
                "reward":   round(reward, 3),
                "score":    result.observation.score,
                "feedback": result.observation.feedback,
                "done":     result.done,
            }), flush=True)

            if result.done:
                break

    # [END] log — required by judges
    print(json.dumps({
        "event":        "[END]",
        "total_reward": round(total_reward, 3),
        "steps":        step,
        "avg_reward":   round(total_reward / max(step, 1), 3),
    }), flush=True)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_episode())