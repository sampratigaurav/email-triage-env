"""
validate.py — Self-validation script for email_triage_env.

Checks the environment against all OpenEnv spec requirements and
prints a PASS / FAIL report. Run before submitting to catch issues early.

Usage:
    python validate.py                        # validates against live HF Space
    python validate.py --url http://localhost:7860   # validates locally
"""

import sys
import os
import json
import time
import asyncio
import argparse

# ── Colour helpers (works on Windows too via fallback) ────────────────────────
try:
    import colorama; colorama.init()
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""

PASS  = f"{GREEN}✓ PASS{RESET}"
FAIL  = f"{RED}✗ FAIL{RESET}"
WARN  = f"{YELLOW}⚠ WARN{RESET}"
SKIP  = f"{CYAN}– SKIP{RESET}"

DEFAULT_URL = "https://sampratigaurav-email-triage-env.hf.space"

results: list[dict] = []


def check(name: str, passed: bool, detail: str = "", warn: bool = False):
    status = (WARN if warn else FAIL) if not passed else PASS
    label  = "WARN" if (warn and not passed) else ("PASS" if passed else "FAIL")
    results.append({"name": name, "status": label, "detail": detail})
    detail_str = f"  → {detail}" if detail else ""
    print(f"  {status}  {name}{detail_str}")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def get(session, url: str) -> tuple[int, dict]:
    import aiohttp
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            return r.status, await r.json()
    except Exception as e:
        return 0, {"error": str(e)}


async def post(session, url: str, body: dict) -> tuple[int, dict]:
    import aiohttp
    try:
        async with session.post(
            url, json=body,
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"Content-Type": "application/json"},
        ) as r:
            return r.status, await r.json()
    except Exception as e:
        return 0, {"error": str(e)}


# ── Validation suites ─────────────────────────────────────────────────────────

async def validate_health(session, base: str):
    print(f"\n{BOLD}[1] Health & Connectivity{RESET}")
    status, data = await get(session, f"{base}/health")
    check("Server reachable", status == 200, f"HTTP {status}")
    check("Health returns 'healthy'",
          data.get("status") == "healthy",
          f"got: {data.get('status')}")


async def validate_reset(session, base: str) -> dict | None:
    print(f"\n{BOLD}[2] reset() — Initial Observation{RESET}")
    status, data = await post(session, f"{base}/reset", {})
    check("POST /reset returns 200", status == 200, f"HTTP {status}")
    if status != 200:
        return None

    obs = data.get("observation") or data
    required_obs_fields = [
        "email_subject", "email_body", "sender",
        "task_description", "feedback", "score", "done",
    ]
    for field in required_obs_fields:
        check(f"  Observation has '{field}'", field in obs, f"value: {repr(obs.get(field, 'MISSING'))[:60]}")

    check("score == 0.0 on reset",      obs.get("score") == 0.0,  f"got {obs.get('score')}")
    check("done == False on reset",     obs.get("done") == False, f"got {obs.get('done')}")
    check("email_subject non-empty",    bool(obs.get("email_subject")), obs.get("email_subject", "")[:50])
    check("email_body non-empty",       bool(obs.get("email_body")),    obs.get("email_body", "")[:50])
    check("sender non-empty",           bool(obs.get("sender")),        obs.get("sender", ""))

    return data


async def validate_step(session, base: str, reset_data: dict):
    print(f"\n{BOLD}[3] step() — Action & Reward{RESET}")

    session_id = reset_data.get("session_id")
    body: dict = {
        "action": {
            "classification": "spam",
            "priority": 1,
            "suggested_reply": "no_reply",
        }
    }
    if session_id:
        body["session_id"] = session_id

    status, data = await post(session, f"{base}/step", body)
    check("POST /step returns 200", status == 200, f"HTTP {status}")
    if status != 200:
        return None

    obs = data.get("observation") or data
    reward = data.get("reward") or obs.get("reward") or obs.get("score")

    check("Step returns reward",         reward is not None,           f"reward={reward}")
    check("Reward in [0.0, 1.0]",        reward is not None and 0.0 <= reward <= 1.0, f"reward={reward}")
    check("Step returns done flag",      "done" in data or "done" in obs, f"done={data.get('done', obs.get('done'))}")
    check("Observation has feedback",    bool(obs.get("feedback")),    obs.get("feedback", "")[:80])
    check("reward_breakdown present",    obs.get("reward_breakdown") is not None,
          f"breakdown={obs.get('reward_breakdown')}", warn=True)

    if obs.get("reward_breakdown"):
        bd = obs["reward_breakdown"]
        check("  breakdown has 'classification'", "classification" in bd, f"{bd.get('classification')}")
        check("  breakdown has 'priority'",       "priority"       in bd, f"{bd.get('priority')}")
        check("  breakdown has 'reply_quality'",  "reply_quality"  in bd, f"{bd.get('reply_quality')}")
        total = sum(bd.values())
        check("  breakdown components sum ≤ 1.0", total <= 1.001,  f"sum={total:.3f}")

    return data


async def validate_full_episode(session, base: str):
    print(f"\n{BOLD}[4] Full Episode (3 steps: easy → medium → hard){RESET}")

    _, reset_data = await post(session, f"{base}/reset", {})
    session_id = reset_data.get("session_id")
    DIFFICULTIES = ["easy", "medium", "hard"]
    step_rewards = []
    done_seen = False

    for i, diff in enumerate(DIFFICULTIES):
        # Use a good-faith action for each step
        body: dict = {
            "action": {
                "classification": "urgent",
                "priority": 4,
                "suggested_reply": "I authorize this action and confirm the request.",
            }
        }
        if session_id:
            body["session_id"] = session_id

        status, data = await post(session, f"{base}/step", body)
        obs    = data.get("observation") or data
        reward = data.get("reward") or obs.get("reward") or obs.get("score") or 0.0
        done   = data.get("done") or obs.get("done") or False

        step_rewards.append(reward)
        check(f"  Step {i+1} ({diff}) reward in [0,1]", 0.0 <= reward <= 1.0, f"reward={reward:.3f}")

        if i == len(DIFFICULTIES) - 1:
            done_seen = done
            check("  done=True on final step", done, f"done={done}")

    check("Episode completes in 3 steps",   len(step_rewards) == 3, f"got {len(step_rewards)} rewards")
    check("All step rewards are non-negative", all(r >= 0 for r in step_rewards), str(step_rewards))


async def validate_state(session, base: str):
    print(f"\n{BOLD}[5] state() — Episode State{RESET}")
    status, data = await get(session, f"{base}/state")
    check("GET /state returns 200", status == 200, f"HTTP {status}")
    if status == 200:
        check("state has episode_id",  "episode_id"  in data or bool(data), f"{list(data.keys())[:5]}")
        check("state has step_count",  "step_count"  in data, f"step_count={data.get('step_count')}", warn=True)


async def validate_extra_endpoints(session, base: str):
    print(f"\n{BOLD}[6] Extra Endpoints (bonus){RESET}")

    status, data = await get(session, f"{base}/info")
    check("GET /info returns 200",       status == 200, f"HTTP {status}")
    check("  /info has reward_range",    "reward_range" in data, warn=True)
    check("  /info has action_space",    "action_space" in data, warn=True)
    check("  /info has observation_space","observation_space" in data, warn=True)

    status, data = await get(session, f"{base}/tasks")
    check("GET /tasks returns 200",      status == 200, f"HTTP {status}")
    if status == 200:
        check("  /tasks has easy tasks",   "easy"   in data.get("tasks_by_difficulty", {}), warn=True)
        check("  /tasks has medium tasks", "medium" in data.get("tasks_by_difficulty", {}), warn=True)
        check("  /tasks has hard tasks",   "hard"   in data.get("tasks_by_difficulty", {}), warn=True)
        total = data.get("total_tasks", 0)
        check(f"  /tasks has ≥ 3 tasks (got {total})", total >= 3, warn=True)

    status, data = await get(session, f"{base}/benchmark")
    check("GET /benchmark returns 200",  status == 200, f"HTTP {status}")
    if status == 200:
        check("  /benchmark has oracle avg", "overall_oracle_avg" in data, warn=True)
        check("  /benchmark has summary",    "summary" in data, warn=True)


async def validate_openenv_yaml():
    print(f"\n{BOLD}[7] openenv.yaml{RESET}")
    yaml_path = os.path.join(os.path.dirname(__file__), "openenv.yaml")
    if not os.path.exists(yaml_path):
        check("openenv.yaml exists", False, "file not found")
        return

    check("openenv.yaml exists", True)
    try:
        import yaml
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
        required_keys = ["spec_version", "name", "tasks", "action_space",
                         "observation_space", "reward_range"]
        for key in required_keys:
            check(f"  yaml has '{key}'", key in config, f"value: {repr(config.get(key, 'MISSING'))[:40]}")
        tasks = config.get("tasks", [])
        check(f"  yaml has ≥ 3 tasks (got {len(tasks)})", len(tasks) >= 3)
        diffs = {t.get("difficulty") for t in tasks}
        check("  yaml has easy/medium/hard", {"easy","medium","hard"} <= diffs, f"found: {diffs}")
        rr = config.get("reward_range", [])
        check("  reward_range is [0.0, 1.0]", rr == [0.0, 1.0], f"got: {rr}")
    except ImportError:
        check("yaml parseable (install pyyaml to check)", False,
              "pip install pyyaml", warn=True)
    except Exception as e:
        check("yaml parseable", False, str(e))


# ── Main runner ───────────────────────────────────────────────────────────────

async def run_all(base_url: str):
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  email_triage_env — OpenEnv Validation Report{RESET}")
    print(f"  Target: {base_url}")
    print(f"  Time:   {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"{BOLD}{'='*65}{RESET}")

    try:
        import aiohttp
    except ImportError:
        print(f"\n{RED}ERROR: aiohttp required. Run: pip install aiohttp{RESET}")
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        await validate_health(session, base_url)
        reset_data = await validate_reset(session, base_url)
        if reset_data:
            await validate_step(session, base_url, reset_data)
            await validate_full_episode(session, base_url)
        await validate_state(session, base_url)
        await validate_extra_endpoints(session, base_url)

    await validate_openenv_yaml()

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for r in results if r["status"] == "PASS")
    warned = sum(1 for r in results if r["status"] == "WARN")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total  = len(results)

    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  SUMMARY{RESET}")
    print(f"  {GREEN}{passed} passed{RESET}  |  {YELLOW}{warned} warnings{RESET}  |  {RED}{failed} failed{RESET}  |  {total} total checks")

    if failed == 0:
        print(f"\n  {GREEN}{BOLD}✓ All required checks passed. Environment is submission-ready.{RESET}")
    else:
        print(f"\n  {RED}{BOLD}✗ {failed} check(s) failed. Fix before submitting.{RESET}")
        failed_names = [r["name"] for r in results if r["status"] == "FAIL"]
        for name in failed_names:
            print(f"    • {name}")

    print(f"{BOLD}{'='*65}{RESET}\n")
    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate email_triage_env against OpenEnv spec.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL of the environment server")
    args = parser.parse_args()

    ok = asyncio.run(run_all(args.url.rstrip("/")))
    sys.exit(0 if ok else 1)