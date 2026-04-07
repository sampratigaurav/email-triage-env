import random
from uuid import uuid4
from typing import List, Dict, Any, Optional

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

# Seed for reproducible task sampling across validation runs
random.seed(42)

try:
    from ..models import EmailTriageAction, EmailTriageObservation
except (ModuleNotFoundError, ImportError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models import EmailTriageAction, EmailTriageObservation


# ── Task Bank ──────────────────────────────────────────────────────────────────
# Each task may optionally carry:
#   thread_context  — list of prior messages the agent can read
#   adversarial     — True when the email is deliberately deceptive
#   required_reply_keywords — list that must appear in the reply for full marks

TASKS: Dict[str, List[Dict[str, Any]]] = {
    "easy": [
        {
            "email_subject": "CONGRATULATIONS! You won $1,000,000!!!",
            "email_body": "Click here NOW to claim your prize. Limited time offer. Send your bank details.",
            "sender": "prizes@totally-legit-money.com",
            "correct_classification": "spam",
            "correct_priority": 1,
            "needs_reply": False,
        },
        {
            "email_subject": "Weekly newsletter - Tech Digest #42",
            "email_body": "This week in tech: AI news, new framework releases, and a tutorial on Python decorators.",
            "sender": "newsletter@techdigest.io",
            "correct_classification": "newsletter",
            "correct_priority": 1,
            "needs_reply": False,
        },
        {
            "email_subject": "You have been selected for a FREE iPhone 15!",
            "email_body": "Dear valued customer, click the link below to claim your free iPhone. Offer expires tonight!",
            "sender": "freestuff@click-here-now.biz",
            "correct_classification": "spam",
            "correct_priority": 1,
            "needs_reply": False,
        },
        {
            "email_subject": "Monthly digest - Design Inspiration #18",
            "email_body": "Hello! Here are this month's top design trends, color palettes, and UI inspiration links.",
            "sender": "digest@designweekly.com",
            "correct_classification": "newsletter",
            "correct_priority": 1,
            "needs_reply": False,
        },
    ],

    "medium": [
        {
            "email_subject": "Meeting reschedule request",
            "email_body": "Hi, I need to move our 3pm meeting tomorrow. Are you free at 4pm or 5pm instead? Please let me know ASAP.",
            "sender": "manager@company.com",
            "correct_classification": "urgent",
            "correct_priority": 4,
            "needs_reply": True,
        },
        {
            "email_subject": "Invoice #4521 - Payment Due",
            "email_body": "Please find attached invoice #4521 for $2,400. Payment is due within 30 days. Thank you for your business.",
            "sender": "billing@vendor.com",
            "correct_classification": "normal",
            "correct_priority": 3,
            "needs_reply": True,
        },
        {
            "email_subject": "Project deadline reminder",
            "email_body": "Just a reminder that the Q2 report is due this Friday. Please make sure your sections are submitted by Thursday EOD for review.",
            "sender": "projectlead@company.com",
            "correct_classification": "urgent",
            "correct_priority": 4,
            "needs_reply": True,
        },
        {
            "email_subject": "New employee onboarding - action required",
            "email_body": "A new team member joins next Monday. Please ensure their laptop, access cards, and system accounts are ready by Friday.",
            "sender": "hr@company.com",
            "correct_classification": "normal",
            "correct_priority": 3,
            "needs_reply": True,
        },
        {
            "email_subject": "Client complaint - order delayed",
            "email_body": "I placed order #8823 two weeks ago and it still has not arrived. This is unacceptable. I need an update immediately.",
            "sender": "angry.customer@gmail.com",
            "correct_classification": "urgent",
            "correct_priority": 4,
            "needs_reply": True,
        },
        # ── Thread-aware medium task ──────────────────────────────────────────
        {
            "email_subject": "Re: Re: Quarterly budget review",
            "email_body": (
                "Following up again — I still haven't received the updated figures. "
                "The board meeting is tomorrow morning and I need the numbers by tonight."
            ),
            "sender": "cfo@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "thread_context": [
                {
                    "from": "cfo@company.com",
                    "subject": "Quarterly budget review",
                    "body": "Can you send me the updated Q3 figures when you get a chance?",
                },
                {
                    "from": "you@company.com",
                    "subject": "Re: Quarterly budget review",
                    "body": "Sure, I'll have them to you by end of week.",
                },
            ],
        },
    ],

    "hard": [
        # ── Original hard tasks ───────────────────────────────────────────────
        {
            "email_subject": "Urgent: Production server down - immediate action required",
            "email_body": (
                "Our primary database server went offline at 14:32 UTC. 3,000 users affected. "
                "The on-call engineer is unreachable. We need authorization to spin up the backup "
                "server. This will cost approximately $500/hour. Please respond immediately."
            ),
            "sender": "sre-team@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "required_reply_keywords": ["authorize", "backup", "approve"],
        },
        {
            "email_subject": "Re: Re: Re: Team lunch next Friday?",
            "email_body": (
                "Hey, still trying to figure out if Friday works for everyone. Last count was 8 people. "
                "The Thai place has a minimum of 10. Should we switch restaurants or try to get more people?"
            ),
            "sender": "colleague@company.com",
            "correct_classification": "normal",
            "correct_priority": 2,
            "needs_reply": True,
        },
        {
            "email_subject": "Security breach detected - immediate response needed",
            "email_body": (
                "Our monitoring system detected unauthorized access to the customer database at 03:14 UTC. "
                "Approximately 50,000 records may be compromised. Legal and PR teams have been notified. "
                "We need your authorization to take the system offline and begin incident response protocol."
            ),
            "sender": "security@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "required_reply_keywords": ["authorize", "offline", "confirm"],
        },
        {
            "email_subject": "Budget approval needed for Q3 marketing campaign",
            "email_body": (
                "Hi, the Q3 campaign proposal is attached. We need budget approval of $45,000 by end of week "
                "to secure vendor slots. The campaign targets 200,000 users and projected ROI is 340%. "
                "Please review and approve or suggest amendments."
            ),
            "sender": "marketing.director@company.com",
            "correct_classification": "urgent",
            "correct_priority": 4,
            "needs_reply": True,
            "required_reply_keywords": ["approve", "budget", "confirm"],
        },
        {
            "email_subject": "Fwd: Fwd: Fwd: Funny cat video",
            "email_body": (
                "Haha you have to see this! Forwarded 4 times. "
                "Original message: check out this hilarious compilation of cats falling off things."
            ),
            "sender": "uncle.bob@hotmail.com",
            "correct_classification": "spam",
            "correct_priority": 1,
            "needs_reply": False,
        },

        # ── ADVERSARIAL hard tasks (new) ──────────────────────────────────────
        # Looks like spam but is actually urgent — common agent failure mode
        {
            "email_subject": "You have 24 hours to act or lose access FOREVER",
            "email_body": (
                "This is an automated security alert from IT Security. "
                "Unusual login activity was detected on your corporate account from IP 185.220.101.47 (Moscow, RU). "
                "If this was not you, you must reset your password within 24 hours or your account will be "
                "suspended to protect company data. Reply CONFIRM to begin the reset process."
            ),
            "sender": "it-security@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "required_reply_keywords": ["confirm", "reset", "security"],
            "adversarial": True,
            "adversarial_hint": (
                "This email uses spam-like language ('24 hours', 'FOREVER') but comes from a legitimate "
                "internal domain and describes a real security threat. Classifying it as spam is wrong."
            ),
        },
        # Looks urgent but is actually a newsletter
        {
            "email_subject": "CRITICAL UPDATE: Your AI workflow is about to change forever",
            "email_body": (
                "Dear reader, in this week's edition of The AI Insider we cover: "
                "1) How GPT-5 will reshape enterprise workflows, "
                "2) The 5 prompting mistakes killing your productivity, "
                "3) Exclusive: Interview with a leading AI researcher. "
                "Click to read the full issue — 47,000 subscribers can't be wrong!"
            ),
            "sender": "editor@the-ai-insider.substack.com",
            "correct_classification": "newsletter",
            "correct_priority": 1,
            "needs_reply": False,
            "adversarial": True,
            "adversarial_hint": (
                "Despite urgent-sounding language ('CRITICAL UPDATE', 'forever'), "
                "this is a newsletter from a Substack publication. No action is needed."
            ),
        },
        # Polite-sounding email that is actually high priority
        {
            "email_subject": "Quick question about the Henderson contract",
            "email_body": (
                "Hi, hope you're well! Just a quick one — the Henderson contract renewal is up for signature. "
                "It's worth $2.3M annually. The client's legal team mentioned they have another vendor offer "
                "on the table and need our signed copy by close of business today to proceed with us. "
                "No rush if you're busy, but wanted to flag it! Thanks."
            ),
            "sender": "sales.lead@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "required_reply_keywords": ["sign", "contract", "confirm"],
            "adversarial": True,
            "adversarial_hint": (
                "The casual tone ('Quick question', 'No rush') masks an extremely time-sensitive "
                "$2.3M contract deadline. An agent that reads tone rather than content will under-prioritize this."
            ),
        },
        # Thread-aware adversarial: context reveals the sender is NOT who they claim
        {
            "email_subject": "Re: Wire transfer approval — urgent",
            "email_body": (
                "Hi, following up on my earlier message. Please process the $87,000 wire transfer to "
                "account ending 4821 as discussed. The acquisition closes today. Approve immediately."
            ),
            "sender": "ceo.office@company-mail.net",
            "correct_classification": "spam",
            "correct_priority": 1,
            "needs_reply": False,
            "required_reply_keywords": [],
            "adversarial": True,
            "adversarial_hint": (
                "Classic CEO fraud / BEC attack. The sender domain is 'company-mail.net' not 'company.com'. "
                "No prior thread exists. No reply should be sent — this is spam/phishing."
            ),
            "thread_context": [
                {
                    "from": "system@company.com",
                    "subject": "Domain alert",
                    "body": (
                        "Note: The domain 'company-mail.net' is NOT a registered company domain. "
                        "Our CEO's address is ceo@company.com. Treat emails from this domain with suspicion."
                    ),
                },
            ],
        },
    ],
}

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]


# ── Environment ────────────────────────────────────────────────────────────────

class EmailTriageEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._current_task: Optional[Dict[str, Any]] = None
        self._difficulty = "easy"
        # Thread context accumulated across the episode so the agent can
        # reference prior decisions (mirrors real-world inbox state).
        self._episode_thread: List[Dict[str, Any]] = []

    def reset(self, difficulty: str = "easy") -> EmailTriageObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        start_diff = difficulty if difficulty in DIFFICULTY_LEVELS else "easy"
        self._difficulty = start_diff
        self._episode_thread = []
        self._current_task = random.choice(TASKS[start_diff])

        return self._make_observation(
            task=self._current_task,
            feedback="New episode started. Triage the email above.",
            score=0.0,
            reward=0.0,
            done=False,
            reward_breakdown=None,
        )

    def step(self, action: EmailTriageAction) -> EmailTriageObservation:
        self._state.step_count += 1
        task = self._current_task

        score, breakdown = self._grade_action(action, task)

        # Record this email + agent decision in the episode thread
        self._episode_thread.append({
            "step": self._state.step_count,
            "difficulty": self._difficulty,
            "email_subject": task["email_subject"],
            "agent_classification": action.classification,
            "agent_priority": action.priority,
            "score": score,
        })

        current_idx = DIFFICULTY_LEVELS.index(self._difficulty)
        done = current_idx >= len(DIFFICULTY_LEVELS) - 1

        # ── Build feedback with optional mistake explainer ─────────────────
        mistake_hint = self._explain_mistake(action, task, score, breakdown)

        if not done:
            next_difficulty = DIFFICULTY_LEVELS[current_idx + 1]
            self._difficulty = next_difficulty
            self._current_task = random.choice(TASKS[next_difficulty])
            feedback = (
                f"Score: {score:.2f} | "
                f"classification={breakdown['classification']:.2f}, "
                f"priority={breakdown['priority']:.2f}, "
                f"reply={breakdown['reply_quality']:.2f}. "
                f"Next task: {next_difficulty} difficulty."
            )
            if mistake_hint:
                feedback += f" | HINT: {mistake_hint}"
            next_task = self._current_task
        else:
            feedback = (
                f"Final score: {score:.2f} | "
                f"classification={breakdown['classification']:.2f}, "
                f"priority={breakdown['priority']:.2f}, "
                f"reply={breakdown['reply_quality']:.2f}. "
                f"Episode complete!"
            )
            if mistake_hint:
                feedback += f" | HINT: {mistake_hint}"
            next_task = task

        return self._make_observation(
            task=next_task,
            feedback=feedback,
            score=score,
            reward=score,
            done=done,
            reward_breakdown=breakdown,
        )

    @property
    def state(self) -> State:
        return self._state

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_observation(
        self,
        task: Dict[str, Any],
        feedback: str,
        score: float,
        reward: float,
        done: bool,
        reward_breakdown: Optional[Dict[str, float]],
    ) -> EmailTriageObservation:
        """Build an observation, injecting thread context when present."""

        thread = task.get("thread_context", [])
        task_desc = (
            "Triage this email. Classify it as one of: spam, urgent, normal, newsletter. "
            "Set a priority from 1 (lowest) to 5 (highest). "
            "Write a short suggested_reply, or write 'no_reply' if no reply is needed."
        )

        if thread:
            thread_text = "\n".join(
                f"[{i+1}] From: {m['from']} | Subject: {m['subject']}\n    {m['body']}"
                for i, m in enumerate(thread)
            )
            task_desc = (
                f"{task_desc}\n\n"
                f"--- THREAD CONTEXT (read before triaging) ---\n{thread_text}\n"
                f"--- END THREAD CONTEXT ---"
            )

        return EmailTriageObservation(
            email_subject=task["email_subject"],
            email_body=task["email_body"],
            sender=task["sender"],
            task_description=task_desc,
            feedback=feedback,
            score=score,
            reward=reward,
            done=done,
            reward_breakdown=reward_breakdown,
        )

    def _explain_mistake(
        self,
        action: EmailTriageAction,
        task: Dict[str, Any],
        score: float,
        breakdown: Dict[str, float],
    ) -> str:
        """
        When score < 0.5, return a concise human-readable explanation of
        what the agent got wrong and what the correct answer was.
        This teaches the agent (and shows judges the grading is principled).
        """
        if score >= 0.5:
            return ""  # No hint needed for good answers

        hints = []
        given_class   = action.classification.lower().strip()
        correct_class = task["correct_classification"]
        correct_p     = task["correct_priority"]
        given_p       = max(1, min(5, int(action.priority))) if action.priority else 3

        # Classification mistake
        if breakdown["classification"] < 0.5:
            if task.get("adversarial"):
                hint = task.get("adversarial_hint", "")
                if hint:
                    hints.append(f"ADVERSARIAL — {hint}")
                else:
                    hints.append(
                        f"Adversarial email: looked like '{given_class}' "
                        f"but correct answer is '{correct_class}'."
                    )
            elif task.get("thread_context"):
                hints.append(
                    f"Thread context changes the answer: correct classification "
                    f"is '{correct_class}', not '{given_class}'. Read prior messages."
                )
            else:
                hints.append(
                    f"Classification wrong: got '{given_class}', "
                    f"expected '{correct_class}'."
                )

        # Priority mistake
        if breakdown["priority"] < 0.2 and abs(given_p - correct_p) >= 2:
            hints.append(
                f"Priority too far off: got {given_p}, "
                f"expected {correct_p} (diff={abs(given_p - correct_p)})."
            )

        # Reply mistake
        if breakdown["reply_quality"] < 0.1:
            needs_reply = task.get("needs_reply", False)
            gave_reply  = action.suggested_reply.strip().lower() != "no_reply"
            if needs_reply and not gave_reply:
                kws = task.get("required_reply_keywords", [])
                kw_str = f" Include keywords: {kws}." if kws else ""
                hints.append(f"A reply was required but none was given.{kw_str}")
            elif not needs_reply and gave_reply:
                hints.append("No reply was needed — sending one wastes attention.")

        return " | ".join(hints) if hints else ""

    def _grade_action(
        self, action: EmailTriageAction, task: Dict[str, Any]
    ) -> tuple[float, Dict[str, float]]:
        """
        Returns (total_score, breakdown_dict).
        breakdown keys: classification, priority, reply_quality
        """
        breakdown: Dict[str, float] = {
            "classification": 0.0,
            "priority": 0.0,
            "reply_quality": 0.0,
        }

        # ── Classification — worth 0.5 ─────────────────────────────────────
        given_class = action.classification.lower().strip()
        correct_class = task["correct_classification"]

        if given_class == correct_class:
            breakdown["classification"] = 0.5
        else:
            # Partial credit for close misses (urgent ↔ normal)
            partial_credit_pairs = {("urgent", "normal"), ("normal", "urgent")}
            if (given_class, correct_class) in partial_credit_pairs:
                breakdown["classification"] = 0.15
            # Adversarial penalty: misclassifying an adversarial email costs extra
            if task.get("adversarial") and given_class != correct_class:
                breakdown["classification"] = max(0.0, breakdown["classification"] - 0.1)

        # ── Priority — worth 0.3 ──────────────────────────────────────────
        correct_p = task["correct_priority"]
        try:
            given_p = max(1, min(5, int(action.priority)))
        except (ValueError, TypeError):
            given_p = 3

        diff = abs(given_p - correct_p)
        if diff == 0:
            breakdown["priority"] = 0.3
        elif diff == 1:
            breakdown["priority"] = 0.2
        elif diff == 2:
            breakdown["priority"] = 0.1

        # ── Reply quality — worth 0.2 ─────────────────────────────────────
        needs_reply = task.get("needs_reply", False)
        reply = action.suggested_reply.strip()
        gave_reply = reply.lower() != "no_reply" and len(reply) > 5

        if needs_reply and gave_reply:
            breakdown["reply_quality"] += 0.1
            if len(reply) > 20:
                breakdown["reply_quality"] += 0.05
            required_keywords = task.get("required_reply_keywords", [])
            if required_keywords:
                reply_lower = reply.lower()
                matched = sum(1 for kw in required_keywords if kw in reply_lower)
                breakdown["reply_quality"] += 0.05 * (matched / len(required_keywords))
            else:
                breakdown["reply_quality"] += 0.05
        elif not needs_reply and not gave_reply:
            breakdown["reply_quality"] = 0.2
        elif not needs_reply and gave_reply:
            breakdown["reply_quality"] = 0.05  # penalise unnecessary reply

        total = round(min(sum(breakdown.values()), 1.0), 2)
        breakdown = {k: round(v, 2) for k, v in breakdown.items()}
        return total, breakdown