"""
Inference script for Email Triage Environment.
Judges run this file to evaluate the submission.

Runs 3 episodes to demonstrate agent learning across episodes.
Logs output in the required [START] / [STEP] / [END] format.

Uses only stdlib (urllib) + openai — no httpx, no local imports needed.
"""

import os
import json
import time
import random
import asyncio
import urllib.request
import urllib.error
from typing import List

from openai import OpenAI

random.seed(42)

# ── Configuration ──────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN")
ENV_URL      = os.environ.get("ENV_URL",      "https://sampratigaurav-email-triage-env.hf.space")
NUM_EPISODES = int(os.environ.get("NUM_EPISODES", "3"))

llm = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

experience_buffer: List[dict] = []


# ── HTTP helper (stdlib only) ──────────────────────────────────────────────────

def http_post(path: str, body: dict) -> dict:
    """Synchronous POST using only stdlib urllib."""
    url  = f"{ENV_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── LLM agent ─────────────────────────────────────────────────────────────────

def ask_llm(email_subject, email_body, sender, task_desc, episode):
    few_shot_text = ""
    if experience_buffer:
        examples = experience_buffer[-6:]
        lines = ["\nExamples of correct past decisions:\n"]
        for ex in examples:
            lines.append(
                f"  Email: \"{ex['subject']}\" from {ex['sender']}\n"
                f"  -> classification={ex['classification']}, priority={ex['priority']}, score={ex['score']}\n"
            )
        few_shot_text = "\n".join(lines)

    prompt = (
        f"You are an expert email triage assistant. Episode {episode}.\n"
        f"Task: {task_desc}\n"
        f"{few_shot_text}\n"
        f"Email:\nFrom: {sender}\nSubject: {email_subject}\nBody:\n{email_body}\n\n"
        "Respond with ONLY valid JSON, no markdown, no explanation:\n"
        '{{"classification": "spam", "priority": 1, "suggested_reply": "no_reply"}}\n\n'
        "Rules:\n"
        "- classification: spam, urgent, normal, or newsletter\n"
        "- priority: integer 1-5\n"
        "- suggested_reply: short string or exactly 'no_reply'\n"
        "- For urgent emails needing reply use keywords: authorize, confirm, approve\n"
        "- Spam-like language from legit internal domain = urgent\n"
        "- Wire transfer from spoofed domain = spam\n"
    )

    response = llm.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=max(0.3 - (episode - 1) * 0.1, 0.05),
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = [l for l in raw.split("\n") if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()
    return json.loads(raw)


def safe_ask_llm(email_subject, email_body, sender, task_desc, episode):
    try:
        return ask_llm(email_subject, email_body, sender, task_desc, episode)
    except Exception as e:
        print(json.dumps({"event": "[WARN]", "message": f"LLM error: {e}, using fallback"}), flush=True)
        return {"classification": "normal", "priority": 3, "suggested_reply": "Thank you, I will review this."}


# ── Single episode (sync HTTP, wrapped in async) ───────────────────────────────

async def run_episode(episode_num: int) -> dict:
    """Run one full episode. Uses stdlib urllib — no external HTTP deps."""
    episode_rewards: List[float] = []
    step_details: List[dict] = []
    step = 0
    DIFFICULTIES = ["easy", "medium", "hard"]

    # Reset
    reset_resp = await asyncio.get_event_loop().run_in_executor(
        None, lambda: http_post("/reset", {})
    )
    obs        = reset_resp.get("observation") or reset_resp
    session_id = reset_resp.get("session_id")

    while True:
        current_difficulty = DIFFICULTIES[min(step, 2)]

        action_dict = safe_ask_llm(
            email_subject=obs.get("email_subject", ""),
            email_body=obs.get("email_body", ""),
            sender=obs.get("sender", ""),
            task_desc=obs.get("task_description", ""),
            episode=episode_num,
        )

        step_body: dict = {
            "action": {
                "classification":  action_dict["classification"],
                "priority":        action_dict["priority"],
                "suggested_reply": action_dict["suggested_reply"],
            }
        }
        if session_id:
            step_body["session_id"] = session_id

        step_resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda b=step_body: http_post("/step", b)
        )

        step    += 1
        next_obs = step_resp.get("observation") or step_resp
        reward   = (
            step_resp.get("reward")
            or next_obs.get("reward")
            or next_obs.get("score")
            or 0.0
        )
        done      = step_resp.get("done") or next_obs.get("done") or False
        breakdown = next_obs.get("reward_breakdown")
        feedback  = next_obs.get("feedback", "")

        episode_rewards.append(reward)

        print(json.dumps({
            "event":            "[STEP]",
            "step":             step,
            "action":           action_dict,
            "reward":           round(float(reward), 3),
            "done":             done,
            "episode":          episode_num,
            "difficulty":       current_difficulty,
            "reward_breakdown": breakdown,
            "score":            next_obs.get("score", reward),
            "feedback":         feedback,
        }), flush=True)

        step_details.append({
            "step":           step,
            "difficulty":     current_difficulty,
            "subject":        obs.get("email_subject", "")[:45],
            "classification": action_dict["classification"],
            "priority":       action_dict["priority"],
            "reward":         round(float(reward), 3),
            "breakdown":      breakdown or {},
        })

        if reward >= 0.7:
            experience_buffer.append({
                "subject":        obs.get("email_subject", ""),
                "sender":         obs.get("sender", ""),
                "classification": action_dict["classification"],
                "priority":       action_dict["priority"],
                "score":          round(float(reward), 2),
            })

        obs = next_obs
        if done:
            break

    total_reward = sum(episode_rewards)
    avg_reward   = total_reward / max(len(episode_rewards), 1)
    return {
        "episode":      episode_num,
        "steps":        step,
        "total_reward": round(total_reward, 3),
        "avg_reward":   round(avg_reward, 3),
        "per_step":     [round(float(r), 3) for r in episode_rewards],
        "step_details": step_details,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    print(json.dumps({
        "event":        "[START]",
        "env":          "email_triage_env",
        "model":        MODEL_NAME,
        "num_episodes": NUM_EPISODES,
        "timestamp":    time.time(),
    }), flush=True)

    episode_summaries = []

    for ep in range(1, NUM_EPISODES + 1):
        print(json.dumps({
            "event":                  "[EPISODE_START]",
            "episode":                ep,
            "experience_buffer_size": len(experience_buffer),
        }), flush=True)

        summary = await run_episode(ep)
        episode_summaries.append(summary)

        print(json.dumps({
            "event":        "[EPISODE_END]",
            "episode":      ep,
            "total_reward": summary["total_reward"],
            "avg_reward":   summary["avg_reward"],
            "per_step":     summary["per_step"],
        }), flush=True)

        await asyncio.sleep(1)

    avg_rewards  = [s["avg_reward"] for s in episode_summaries]
    improvement  = round(avg_rewards[-1] - avg_rewards[0], 3) if len(avg_rewards) > 1 else 0.0
    reward_curve = " -> ".join(str(r) for r in avg_rewards)

    print(json.dumps({
        "event":           "[END]",
        "total_episodes":  NUM_EPISODES,
        "reward_curve":    reward_curve,
        "improvement":     improvement,
        "episode_details": episode_summaries,
        "note":            "Agent improves via few-shot experience injection across episodes.",
    }), flush=True)

    # Human-readable bar chart
    print("\n" + "=" * 65, flush=True)
    print("  EMAIL TRIAGE AGENT - LEARNING CURVE", flush=True)
    print("=" * 65, flush=True)
    for s in episode_summaries:
        filled = int(s["avg_reward"] * 30)
        bar    = "#" * filled + "." * (30 - filled)
        print(f"  Ep {s['episode']}  [{bar}]  {s['avg_reward']:.3f}", flush=True)
    sign = "+" if improvement >= 0 else ""
    print(f"\n  Improvement ep1 -> ep{NUM_EPISODES}: {sign}{improvement:.3f}", flush=True)
    print(f"  Experience buffer: {len(experience_buffer)} examples stored", flush=True)
    print("=" * 65, flush=True)


if __name__ == "__main__":
    asyncio.run(main())