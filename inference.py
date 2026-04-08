"""
Inference script for Email Triage Environment.
Judges run this file to evaluate the submission.

Runs 3 episodes demonstrating agent learning across episodes.
Logs output in the required [START] / [STEP] / [END] format.

Dependencies: openai (pre-installed), stdlib only for HTTP.
No httpx, no local package imports required.
"""

import os
import json
import time
import random
import asyncio
import urllib.request
import urllib.error
from typing import List, Optional

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


# ── HTTP helper — stdlib urllib, with retry for cold-start ────────────────────

def http_post_sync(path: str, body: dict, retries: int = 3) -> dict:
    """POST via stdlib urllib with retry. No external dependencies needed."""
    url  = ENV_URL.rstrip("/") + path
    data = json.dumps(body).encode("utf-8")
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))  # back-off: 3s, 6s
    raise RuntimeError(f"HTTP POST {path} failed after {retries} attempts: {last_err}")


# ── Helpers to safely extract fields from response ────────────────────────────

def get_obs(resp: dict) -> dict:
    """Extract observation dict from reset/step response."""
    return resp.get("observation") or resp


def get_reward(resp: dict, obs: dict) -> float:
    """Extract reward — handles None from server."""
    r = resp.get("reward") or obs.get("reward") or obs.get("score")
    return float(r) if r is not None else 0.0


def get_done(resp: dict, obs: dict) -> bool:
    return bool(resp.get("done") or obs.get("done") or False)


# ── LLM agent ─────────────────────────────────────────────────────────────────

def ask_llm(email_subject: str, email_body: str, sender: str,
            task_desc: str, episode: int) -> dict:
    few_shot = ""
    if experience_buffer:
        lines = ["\nExamples of high-scoring past decisions:\n"]
        for ex in experience_buffer[-6:]:
            lines.append(
                f"  Subject: \"{ex['subject']}\" from {ex['sender']}\n"
                f"  -> classification={ex['classification']}, "
                f"priority={ex['priority']}, score={ex['score']}\n"
            )
        few_shot = "\n".join(lines)

    prompt = (
        f"You are an expert email triage assistant. Episode {episode}.\n"
        f"Task: {task_desc}\n"
        f"{few_shot}\n"
        f"Triage this email:\n"
        f"From: {sender}\nSubject: {email_subject}\nBody:\n{email_body}\n\n"
        "Respond ONLY with valid JSON (no markdown, no code fences):\n"
        "{\"classification\": \"spam\", \"priority\": 1, \"suggested_reply\": \"no_reply\"}\n\n"
        "Rules:\n"
        "- classification: spam | urgent | normal | newsletter\n"
        "- priority: integer 1 (lowest) to 5 (highest)\n"
        "- suggested_reply: short string or exactly 'no_reply'\n"
        "- Urgent emails needing reply: include keywords authorize/confirm/approve\n"
        "- Spam-like language from internal company domain = urgent, not spam\n"
        "- Wire transfer request from non-company domain = spam (CEO fraud)\n"
    )

    response = llm.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=max(0.3 - (episode - 1) * 0.1, 0.05),
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if model adds them
    if raw.startswith("```"):
        raw = "\n".join(
            l for l in raw.split("\n") if not l.strip().startswith("```")
        ).strip()
    return json.loads(raw)


def safe_ask_llm(email_subject: str, email_body: str, sender: str,
                 task_desc: str, episode: int) -> dict:
    try:
        return ask_llm(email_subject, email_body, sender, task_desc, episode)
    except Exception as e:
        print(json.dumps({"event": "[WARN]",
                          "message": f"LLM error: {e}, using fallback"}), flush=True)
        return {
            "classification": "normal",
            "priority": 3,
            "suggested_reply": "Thank you for your email. I will review this shortly.",
        }


# ── Single episode ─────────────────────────────────────────────────────────────

async def run_episode(episode_num: int) -> dict:
    """
    Run one full episode.
    HTTP is synchronous (urllib) executed in thread pool — no external deps.
    Uses asyncio.get_running_loop() (correct for coroutines, py3.10+).
    """
    episode_rewards: List[float] = []
    step_details:    List[dict]  = []
    step = 0
    DIFFICULTIES = ["easy", "medium", "hard"]

    loop = asyncio.get_running_loop()

    # ── Reset ──────────────────────────────────────────────────────────────────
    reset_resp = await loop.run_in_executor(None, http_post_sync, "/reset", {})
    obs = get_obs(reset_resp)

    # ── Step loop ──────────────────────────────────────────────────────────────
    while True:
        current_difficulty = DIFFICULTIES[min(step, len(DIFFICULTIES) - 1)]

        action_dict = safe_ask_llm(
            email_subject=obs.get("email_subject", ""),
            email_body=obs.get("email_body", ""),
            sender=obs.get("sender", ""),
            task_desc=obs.get("task_description", ""),
            episode=episode_num,
        )

        step_body = {
            "action": {
                "classification":  action_dict["classification"],
                "priority":        action_dict["priority"],
                "suggested_reply": action_dict["suggested_reply"],
            }
        }

        step_resp = await loop.run_in_executor(
            None, http_post_sync, "/step", step_body
        )

        step    += 1
        next_obs = get_obs(step_resp)
        reward   = get_reward(step_resp, next_obs)
        done     = get_done(step_resp, next_obs)
        breakdown = next_obs.get("reward_breakdown")
        feedback  = next_obs.get("feedback", "")

        episode_rewards.append(reward)

        # ── Required [STEP] log ────────────────────────────────────────────────
        print(json.dumps({
            "event":            "[STEP]",
            "step":             step,
            "action":           action_dict,
            "reward":           round(reward, 3),
            "done":             done,
            "episode":          episode_num,
            "difficulty":       current_difficulty,
            "reward_breakdown": breakdown,
            "score":            float(next_obs.get("score") or reward),
            "feedback":         feedback,
        }), flush=True)

        step_details.append({
            "step":           step,
            "difficulty":     current_difficulty,
            "subject":        obs.get("email_subject", "")[:50],
            "classification": action_dict["classification"],
            "priority":       action_dict["priority"],
            "reward":         round(reward, 3),
            "breakdown":      breakdown or {},
        })

        # Store high-quality decisions for few-shot injection
        if reward >= 0.7:
            experience_buffer.append({
                "subject":        obs.get("email_subject", ""),
                "sender":         obs.get("sender", ""),
                "classification": action_dict["classification"],
                "priority":       action_dict["priority"],
                "score":          round(reward, 2),
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
        "per_step":     [round(r, 3) for r in episode_rewards],
        "step_details": step_details,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    # ── Required [START] log ───────────────────────────────────────────────────
    print(json.dumps({
        "event":        "[START]",
        "env":          "email_triage_env",
        "model":        MODEL_NAME,
        "num_episodes": NUM_EPISODES,
        "timestamp":    time.time(),
    }), flush=True)

    episode_summaries: List[dict] = []

    for ep in range(1, NUM_EPISODES + 1):

        print(json.dumps({
            "event":                  "[EPISODE_START]",
            "episode":                ep,
            "experience_buffer_size": len(experience_buffer),
        }), flush=True)

        try:
            summary = await run_episode(ep)
        except Exception as e:
            # Never crash the whole script — log and use zero rewards
            print(json.dumps({
                "event":   "[WARN]",
                "episode": ep,
                "message": f"Episode failed: {e}",
            }), flush=True)
            summary = {
                "episode": ep, "steps": 0,
                "total_reward": 0.0, "avg_reward": 0.0,
                "per_step": [], "step_details": [],
            }

        episode_summaries.append(summary)

        print(json.dumps({
            "event":        "[EPISODE_END]",
            "episode":      ep,
            "total_reward": summary["total_reward"],
            "avg_reward":   summary["avg_reward"],
            "per_step":     summary["per_step"],
        }), flush=True)

        if ep < NUM_EPISODES:
            await asyncio.sleep(1)

    avg_rewards  = [s["avg_reward"] for s in episode_summaries]
    improvement  = round(avg_rewards[-1] - avg_rewards[0], 3) if len(avg_rewards) > 1 else 0.0
    reward_curve = " -> ".join(str(r) for r in avg_rewards)

    # ── Required [END] log ────────────────────────────────────────────────────
    print(json.dumps({
        "event":           "[END]",
        "total_episodes":  NUM_EPISODES,
        "reward_curve":    reward_curve,
        "improvement":     improvement,
        "episode_details": episode_summaries,
        "note":            "Agent improves via few-shot experience injection across episodes.",
    }), flush=True)

    # ── Human-readable summary ─────────────────────────────────────────────────
    print("\n" + "=" * 65, flush=True)
    print("  EMAIL TRIAGE AGENT - LEARNING CURVE", flush=True)
    print("=" * 65, flush=True)
    for s in episode_summaries:
        filled = int(s["avg_reward"] * 30)
        bar    = "#" * filled + "." * (30 - filled)
        print(f"  Ep {s['episode']}  [{bar}]  {s['avg_reward']:.3f}", flush=True)
    sign = "+" if improvement >= 0 else ""
    print(f"\n  Improvement ep1->ep{NUM_EPISODES}: {sign}{improvement:.3f}", flush=True)
    print(f"  Experience buffer: {len(experience_buffer)} examples", flush=True)
    print("=" * 65, flush=True)

    # ── Markdown table ─────────────────────────────────────────────────────────
    print("\n  STEP DETAILS\n", flush=True)
    header = f"| {'Ep':>2} | {'Step':>4} | {'Diff':<8} | {'Class':<12} | {'Pri':>3} | {'Reward':>6} |"
    print(header, flush=True)
    print("|" + "-"*4 + "|" + "-"*6 + "|" + "-"*10 + "|" + "-"*14 + "|" + "-"*5 + "|" + "-"*8 + "|", flush=True)
    for s in episode_summaries:
        for d in s.get("step_details", []):
            print(
                f"| {s['episode']:>2} | {d['step']:>4} | {d['difficulty']:<8} "
                f"| {d['classification']:<12} | {d['priority']:>3} | {d['reward']:>6.3f} |",
                flush=True,
            )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main())