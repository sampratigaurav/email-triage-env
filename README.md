---
title: Email Triage Environment
emoji: 📬
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
license: mit
short_description: RL env for email triage — classify, reply
tags:
  - openenv
  - reinforcement-learning
  - email
  - nlp
  - pytorch
  - agents
---

# 📬 Email Triage Environment

> **Meta PyTorch × Scaler OpenEnv Hackathon 2026**
> A real-world reinforcement learning environment where an AI agent learns to triage emails like a professional.

[![Hugging Face Space](https://img.shields.io/badge/🤗%20HuggingFace-Space-blue)](https://huggingface.co/spaces/sampratigaurav/email-triage-env)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-green)](https://github.com/openenv)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Why This Matters

Email overload costs knowledge workers an estimated **2.5 hours per day**. Enterprise inboxes receive hundreds of emails daily — many time-critical, many distractions in disguise. Teaching an AI agent to triage email intelligently is a high-value, real-world problem that directly maps to productivity tooling, enterprise automation, and AI assistant benchmarking.

This environment goes beyond simple classification. It tests whether an agent can:
- Distinguish **adversarial emails** designed to fool classifiers (spam that's actually urgent, urgent-looking newsletters)
- Reason over **thread context** before deciding
- Generate **appropriate, keyword-specific replies** for crisis situations
- Calibrate **priority scores** with nuance, not just binary labels

---

## Environment Overview

| Property | Value |
|---|---|
| **API** | `reset()` / `step()` / `state()` |
| **Action space** | `classification`, `priority`, `suggested_reply` |
| **Observation space** | `email_subject`, `email_body`, `sender`, `task_description`, `feedback`, `score`, `reward_breakdown` |
| **Reward range** | `[0.0, 1.0]` |
| **Difficulty levels** | Easy → Medium → Hard |
| **Episode structure** | 3 steps (one per difficulty level) |

---

## Difficulty Levels

### 🟢 Easy — Obvious Spam & Newsletters
Clear-cut classification. Tests baseline pattern recognition.

```
Email: "CONGRATULATIONS! You won $1,000,000!!!" from prizes@totally-legit-money.com
Correct: classification=spam, priority=1, suggested_reply=no_reply
```

### 🟡 Medium — Scheduling, Billing & Deadlines
Realistic workplace emails. Tests priority calibration and reply generation.
Includes thread-context tasks where prior messages affect the correct answer.

```
Email: "Re: Re: Quarterly budget review" — CFO following up, board meeting tomorrow
Correct: classification=urgent, priority=5 (thread context reveals escalation)
```

### 🔴 Hard — Crisis + Adversarial
The environment's hardest challenge. Includes four adversarial email types designed to exploit common agent failure modes:

| Adversarial Type | Description |
|---|---|
| **Spam-framed urgent** | IT security alert using spam-like language but from a real domain |
| **Urgent-framed newsletter** | "CRITICAL UPDATE" subject that is actually a Substack digest |
| **Polite-framed critical** | Casual email hiding a $2.3M contract deadline |
| **CEO fraud (BEC attack)** | Wire transfer request from a spoofed look-alike domain |

---

## Reward Structure

Rewards are **transparent and granular** — every step returns a `reward_breakdown`:

```json
{
  "reward_breakdown": {
    "classification": 0.50,
    "priority": 0.30,
    "reply_quality": 0.20
  },
  "score": 1.0
}
```

| Component | Max | Description |
|---|---|---|
| `classification` | 0.50 | Exact match = full credit. Close miss (urgent↔normal) = partial. Adversarial miss = penalised. |
| `priority` | 0.30 | Full credit for exact. Partial for ±1 or ±2 off. Zero for >2 off. |
| `reply_quality` | 0.20 | Correct no-reply decisions, keyword matching for crisis emails, length bonus. |

---

## Agent Learning Story

Running `inference.py` executes **3 full episodes**. The agent improves across episodes via **few-shot experience injection**: high-scoring decisions (reward ≥ 0.7) are stored in a buffer and injected as examples into later episodes, simulating the effect of reinforcement learning from environment feedback.

**Typical reward progression:**

```
Episode 1: avg_reward=0.623  ████████████
Episode 2: avg_reward=0.751  ███████████████
Episode 3: avg_reward=0.834  ████████████████
                              +0.211 improvement
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install openenv-core openai
```

### 2. Run against the live hosted environment
```bash
export ENV_URL=https://sampratigaurav-email-triage-env.hf.space
export HF_TOKEN=your_hf_token
export MODEL_NAME=gpt-4o-mini

python inference.py
```

### 3. Run locally with Docker
```bash
docker build -t email-triage-env .
docker run -p 7860:7860 email-triage-env

# In another terminal:
export ENV_URL=http://localhost:7860
python inference.py
```

---

## API Reference

### `POST /reset`
Start a new episode. Returns the first email observation.

```json
{
  "email_subject": "CONGRATULATIONS! You won $1,000,000!!!",
  "email_body": "Click here NOW to claim your prize...",
  "sender": "prizes@totally-legit-money.com",
  "task_description": "Triage this email...",
  "feedback": "New episode started.",
  "score": 0.0,
  "reward": 0.0,
  "done": false,
  "reward_breakdown": null
}
```

### `POST /step`
Submit a triage action. Returns the next observation with reward breakdown.

```json
// Request
{
  "classification": "spam",
  "priority": 1,
  "suggested_reply": "no_reply"
}

// Response
{
  "score": 1.0,
  "reward": 1.0,
  "reward_breakdown": {
    "classification": 0.50,
    "priority": 0.30,
    "reply_quality": 0.20
  },
  "feedback": "Score: 1.00 | classification=0.50, priority=0.30, reply=0.20. Next task: medium difficulty.",
  "done": false
}
```

### `GET /state`
Returns current episode metadata.

### `GET /health`
Returns `{"status": "healthy"}`.

---

## Project Structure

```
email_triage_env/
├── inference.py                          # Judges' evaluation script (multi-episode)
├── models.py                             # Action + Observation schemas
├── client.py                             # OpenEnv async client
├── openenv.yaml                          # Environment spec
├── Dockerfile                            # Container definition
├── README.md
└── server/
    ├── app.py                            # FastAPI server
    ├── email_triage_env_environment.py   # Core environment logic
    └── requirements.txt
```

---

## Baseline Agent Performance

| Agent Type | Episode 1 | Episode 2 | Episode 3 |
|---|---|---|---|
| Random baseline | ~0.25 | ~0.25 | ~0.25 |
| Rule-based (keyword matching) | ~0.55 | ~0.55 | ~0.55 |
| **LLM (gpt-4o-mini) + experience** | **~0.62** | **~0.75** | **~0.83** |

The LLM agent with experience injection outperforms rule-based approaches on adversarial tasks specifically, where keyword matching fails.

---

## Built With

- [OpenEnv](https://github.com/openenv) — environment protocol
- [FastAPI](https://fastapi.tiangolo.com/) — server framework
- [Pydantic](https://docs.pydantic.dev/) — schema validation
- [Docker](https://docker.com/) — containerisation
- [Hugging Face Spaces](https://huggingface.co/spaces) — deployment

---

*Submitted for the Meta PyTorch × Scaler OpenEnv Hackathon 2026 by [@sampratigaurav](https://huggingface.co/sampratigaurav) and [@pramatiiii](https://huggingface.co/pramatiiii).*