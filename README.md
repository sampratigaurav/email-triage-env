---
title: Email Triage Env Environment Server
emoji: 📧
colorFrom: indigo
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

<div align="center">

# 📧 Email Triage Environment

### A production-grade OpenEnv environment for training AI agents to triage emails

[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-blue?style=flat-square)](https://github.com/meta-pytorch/OpenEnv)
[![Python](https://img.shields.io/badge/Python-3.11+-green?style=flat-square)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## Overview

The **Email Triage Environment** is a real-world reinforcement learning environment built on the [OpenEnv](https://github.com/meta-pytorch/OpenEnv) framework. It simulates a realistic workplace email inbox where an AI agent must learn to triage incoming emails — classifying them by type, assigning the correct priority, and generating appropriate replies.

This environment is designed for training and evaluating LLM-based agents on practical, grounded decision-making tasks with clear, verifiable reward signals.

---

## The Task

At each step, the agent receives an email and must respond with three decisions:

| Decision | Type | Options |
|---|---|---|
| `classification` | string | `spam` · `urgent` · `normal` · `newsletter` |
| `priority` | integer | `1` (lowest) → `5` (highest) |
| `suggested_reply` | string | A short reply, or `no_reply` |

The environment then grades the response and returns a reward between `0.0` and `1.0`.

---

## Difficulty Levels

The environment exposes **3 tasks** of increasing difficulty:

### 🟢 Easy — Obvious Classification

Simple, unambiguous emails where the correct action is clear.

*Example: A Nigerian prince offering $1,000,000. Correct response: classify as `spam`, priority `1`, reply `no_reply`.*

### 🟡 Medium — Judgment Required

Emails that require reading context and making priority judgments.

*Example: A manager asking to reschedule a meeting. Correct response: classify as `urgent`, priority `4`, write a reply confirming availability.*

### 🔴 Hard — Complex and Keyword-Sensitive

High-stakes emails where the reply must contain specific authorisation keywords to earn full marks.

*Example: Production server down, 3,000 users affected. Correct response: classify as `urgent`, priority `5`, reply must include words like `authorize`, `backup`, `approve`.*

---

## Reward Function

Rewards are **partial credit** — the agent earns points for each correct sub-decision:
```
Total Reward = Classification (0.5) + Priority (0.3) + Reply Quality (0.2)
```

| Component | Full Credit | Partial Credit | Zero |
|---|---|---|---|
| Classification | Exact match → +0.5 | — | Wrong label → +0.0 |
| Priority | Exact match → +0.3 | Within 1 → +0.15 | Off by 2+ → +0.0 |
| Reply | Correct decision + keywords → +0.2 | Replied but no keywords → +0.1 | Wrong decision → +0.0 |

**Reward range:** `0.0` (completely wrong) → `1.0` (perfect response)

---

## Action Space
```json
{
  "classification": "spam | urgent | normal | newsletter",
  "priority": 1,
  "suggested_reply": "Thank you, I will look into this."
}
```

## Observation Space
```json
{
  "email_subject": "Urgent: Production server down",
  "email_body": "Our database went offline at 14:32 UTC...",
  "sender": "sre-team@company.com",
  "task_description": "Triage this email. Classify, prioritize, and reply.",
  "feedback": "Score: 0.80. Next task is hard difficulty.",
  "score": 0.80
}
```

---

## Quick Start

### Option 1 — Connect to the live Hugging Face Space
```python
from email_triage_env import EmailTriageAction, EmailTriageEnv

with EmailTriageEnv(base_url="https://YOUR-USERNAME-email-triage-env.hf.space") as env:
    result = env.reset()
    print("Email:", result.observation.email_subject)

    result = env.step(EmailTriageAction(
        classification="spam",
        priority=1,
        suggested_reply="no_reply"
    ))

    print("Reward:", result.reward)
    print("Feedback:", result.observation.feedback)
```

### Option 2 — Run locally with Docker
```bash
git clone https://huggingface.co/spaces/YOUR-USERNAME/email_triage_env
cd email_triage_env
docker build -t email_triage_env:latest -f server/Dockerfile .
docker run -p 8000:8000 email_triage_env:latest
python inference.py
```

### Option 3 — Run locally without Docker
```bash
pip install openenv-core uvicorn fastapi
cd email_triage_env
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

---

## Running the Inference Script

The included `inference.py` runs an LLM agent through all 3 difficulty levels and logs structured output.
```bash
export API_BASE_URL=https://api.openai.com/v1
export MODEL_NAME=gpt-4o-mini
export HF_TOKEN=your_huggingface_token
export ENV_URL=http://localhost:8000

python inference.py
```

### Expected output format
```json
{"event": "[START]", "env": "email_triage_env", "model": "gpt-4o-mini"}
{"event": "[STEP]", "step": 1, "reward": 0.8, "score": 0.8, "done": false}
{"event": "[STEP]", "step": 2, "reward": 1.0, "score": 1.0, "done": false}
{"event": "[STEP]", "step": 3, "reward": 0.6, "score": 0.6, "done": true}
{"event": "[END]", "total_reward": 2.4, "steps": 3, "avg_reward": 0.8}
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/reset` | POST | Start a new episode, get first email |
| `/step` | POST | Submit an action, get reward and next email |
| `/state` | GET | Get current episode state |
| `/health` | GET | Health check — must return 200 |
| `/docs` | GET | Interactive Swagger API documentation |
| `/web` | GET | Web UI for exploring the environment |
| `/ws` | WebSocket | Persistent low-latency session |

---

## Project Structure
```
email_triage_env/
│
├── inference.py                         ← Judges run this to score your submission
├── models.py                            ← Action and Observation data models
├── client.py                            ← Python client for connecting to the env
├── openenv.yaml                         ← OpenEnv spec manifest
├── pyproject.toml                       ← Project dependencies
├── README.md                            ← You are here
│
└── server/
    ├── email_triage_env_environment.py  ← Core logic: reset(), step(), grader
    ├── app.py                           ← FastAPI server (HTTP and WebSocket)
    └── Dockerfile                       ← Container definition
```

---

## Environment Specification

| Property | Value |
|---|---|
| Framework | OpenEnv 1.0 |
| Runtime | FastAPI + Uvicorn |
| Deployment | Docker / Hugging Face Spaces |
| Python | 3.11+ |
| Reward Range | 0.0 – 1.0 |
| Episode Length | 3 steps (easy → medium → hard) |
| Max Inference Time | < 20 minutes |
| Memory | < 8 GB |

---

## Built With

- [OpenEnv](https://github.com/meta-pytorch/OpenEnv) — RL environment framework by Meta PyTorch
- [FastAPI](https://fastapi.tiangolo.com/) — API server
- [Pydantic](https://docs.pydantic.dev/) — Data validation
- [Hugging Face Spaces](https://huggingface.co/spaces) — Deployment platform

---

<div align="center">

Built for the **Meta PyTorch × Scaler OpenEnv Hackathon 2026**

</div>