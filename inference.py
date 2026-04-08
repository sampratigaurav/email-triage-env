"""
Inference script for Email Triage Environment.
Meta PyTorch x Scaler OpenEnv Hackathon 2026.

STDOUT FORMAT (exactly as required by the validator):
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
"""

import asyncio
import os
import json
import time
import random
from typing import List, Optional

from openai import OpenAI

random.seed(42)

# ── Configuration ──────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.getenv("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.getenv("HF_TOKEN")
ENV_URL      = os.getenv("ENV_URL",      "https://sampratigaurav-email-triage-env.hf.space")
NUM_EPISODES = int(os.getenv("NUM_EPISODES", "3"))

TASK_NAME  = "email_triage"
BENCHMARK  = "email_triage_env"
MAX_STEPS  = 3   # easy -> medium -> hard
SUCCESS_THRESHOLD = 0.5

experience_buffer: List[dict] = []


# ── Required log helpers (exact format from spec) ─────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool,
             error: Optional[str] = None) -> None:
    error_val = error if error else "null"
    done_val  = str(done).lower()
    print(
        f"[STEP] step={step} action={action} "
        f"reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float,
            rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ── HTTP helper (stdlib urllib — no external deps) ────────────────────────────

import urllib.request
import urllib.error


def http_post(path: str, body: dict, retries: int = 3) -> dict:
    """Synchronous POST via stdlib urllib with retry for cold-start."""
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
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(4 * (attempt + 1))  # 4s, 8s back-off
    raise RuntimeError(
        f"HTTP POST {path} failed after {retries} attempts: {last_err}"
    )


# ── LLM agent ─────────────────────────────────────────────────────────────────

def build_prompt(obs: dict, episode: int) -> str:
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

    return (
        f"You are an expert email triage assistant. Episode {episode}.\n"
        f"Task: {obs.get('task_description', '')}\n"
        f"{few_shot}\n"
        f"Triage this email:\n"
        f"From: {obs.get('sender', '')}\n"
        f"Subject: {obs.get('email_subject', '')}\n"
        f"Body:\n{obs.get('email_body', '')}\n\n"
        "Respond ONLY with valid JSON (no markdown, no code fences):\n"
        "{\"classification\": \"spam\", \"priority\": 1, \"suggested_reply\": \"no_reply\"}\n\n"
        "Rules:\n"
        "- classification: spam | urgent | normal | newsletter\n"
        "- priority: integer 1 (lowest) to 5 (highest)\n"
        "- suggested_reply: short string or exactly 'no_reply'\n"
        "- urgent reply needed: include keywords authorize/confirm/approve\n"
        "- spam-like language from internal company domain = urgent, not spam\n"
        "- wire transfer from non-company domain = spam (CEO fraud)\n"
    )


def call_llm(client: OpenAI, obs: dict, episode: int) -> dict:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": build_prompt(obs, episode)}],
        max_tokens=300,
        temperature=max(0.3 - (episode - 1) * 0.1, 0.05),
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = "\n".join(
            l for l in raw.split("\n") if not l.strip().startswith("```")
        ).strip()
    return json.loads(raw)


def safe_call_llm(client: OpenAI, obs: dict, episode: int) -> dict:
    try:
        return call_llm(client, obs, episode)
    except Exception as e:
        return {
            "classification": "normal",
            "priority": 3,
            "suggested_reply": "Thank you for your email. I will review this.",
        }


# ── Episode runner ─────────────────────────────────────────────────────────────

async def run_episode(client: OpenAI, episode_num: int) -> dict:
    """Run one episode via HTTP REST. Returns episode stats."""
    loop = asyncio.get_running_loop()
    DIFFICULTIES = ["easy", "medium", "hard"]

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        # Reset environment
        reset_resp = await loop.run_in_executor(None, http_post, "/reset", {})
        obs = reset_resp.get("observation") or reset_resp

        for step in range(1, MAX_STEPS + 1):
            action_dict = safe_call_llm(client, obs, episode_num)

            # Format action string for log (compact, no newlines)
            action_str = (
                f"classify={action_dict['classification']},"
                f"priority={action_dict['priority']},"
                f"reply={action_dict['suggested_reply'][:30].replace(' ', '_')}"
            )

            # Step environment
            step_body = {
                "action": {
                    "classification":  action_dict["classification"],
                    "priority":        action_dict["priority"],
                    "suggested_reply": action_dict["suggested_reply"],
                }
            }
            step_resp = await loop.run_in_executor(
                None, http_post, "/step", step_body
            )

            next_obs  = step_resp.get("observation") or step_resp
            reward_raw = step_resp.get("reward")
            if reward_raw is None:
                reward_raw = next_obs.get("reward") or next_obs.get("score") or 0.0
            reward = float(reward_raw)
            done   = bool(step_resp.get("done") or next_obs.get("done") or False)

            rewards.append(reward)
            steps_taken = step

            # Store good decisions for few-shot injection
            if reward >= 0.7:
                experience_buffer.append({
                    "subject":        obs.get("email_subject", ""),
                    "sender":         obs.get("sender", ""),
                    "classification": action_dict["classification"],
                    "priority":       action_dict["priority"],
                    "score":          round(reward, 2),
                })

            # Required [STEP] log
            log_step(step=step, action=action_str, reward=reward,
                     done=done, error=None)

            obs = next_obs
            if done:
                break

        # Score = average reward across steps, clamped to [0, 1]
        score   = min(max(sum(rewards) / max(len(rewards), 1), 0.0), 1.0)
        success = score >= SUCCESS_THRESHOLD

    except Exception as e:
        # Emit at least one [STEP] so output parser has something
        if not rewards:
            rewards = [0.0]
            steps_taken = 1
            log_step(step=1, action="fallback", reward=0.0,
                     done=True, error=str(e)[:80])
        score   = 0.0
        success = False

    finally:
        # Required [END] log — always emitted
        log_end(success=success, steps=steps_taken,
                score=score, rewards=rewards)

    return {
        "episode":      episode_num,
        "steps":        steps_taken,
        "score":        score,
        "success":      success,
        "rewards":      rewards,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    # OpenAI client init INSIDE main() — HF_TOKEN guaranteed set by this point
    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

    all_scores: List[float] = []

    for ep in range(1, NUM_EPISODES + 1):
        result = await run_episode(client, ep)
        all_scores.append(result["score"])
        if ep < NUM_EPISODES:
            await asyncio.sleep(2)

    # Summary bar chart
    improvement = round(all_scores[-1] - all_scores[0], 3) if len(all_scores) > 1 else 0.0
    print("\n" + "=" * 60, flush=True)
    print("  EMAIL TRIAGE - MULTI-EPISODE RESULTS", flush=True)
    print("=" * 60, flush=True)
    for i, s in enumerate(all_scores, 1):
        bar = "#" * int(s * 30) + "." * (30 - int(s * 30))
        print(f"  Ep {i}  [{bar}]  {s:.3f}", flush=True)
    sign = "+" if improvement >= 0 else ""
    print(f"\n  Improvement: {sign}{improvement:.3f}", flush=True)
    print(f"  Avg score:   {sum(all_scores)/max(len(all_scores),1):.3f}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    asyncio.run(main())