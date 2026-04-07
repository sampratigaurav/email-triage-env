import random
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import EmailTriageAction, EmailTriageObservation
except ImportError:
    from models import EmailTriageAction, EmailTriageObservation


TASKS = {
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
    ],
    "hard": [
        {
            "email_subject": "Urgent: Production server down - immediate action required",
            "email_body": "Our primary database server went offline at 14:32 UTC. 3,000 users affected. The on-call engineer is unreachable. We need authorization to spin up the backup server. This will cost approximately $500/hour. Please respond immediately.",
            "sender": "sre-team@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "required_reply_keywords": ["authorize", "backup", "approve"],
        },
        {
            "email_subject": "Re: Re: Re: Team lunch next Friday?",
            "email_body": "Hey, still trying to figure out if Friday works for everyone. Last count was 8 people. The Thai place has a minimum of 10. Should we switch restaurants or try to get more people?",
            "sender": "colleague@company.com",
            "correct_classification": "normal",
            "correct_priority": 2,
            "needs_reply": True,
        },
    ],
}

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]


class EmailTriageEnvironment(Environment):

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._current_task = None
        self._difficulty = "easy"

    def reset(self) -> EmailTriageObservation:
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._difficulty = "easy"
        self._current_task = random.choice(TASKS["easy"])

        return EmailTriageObservation(
            email_subject=self._current_task["email_subject"],
            email_body=self._current_task["email_body"],
            sender=self._current_task["sender"],
            task_description=(
                "Triage this email. Classify it as one of: spam, urgent, normal, newsletter. "
                "Set a priority from 1 (lowest) to 5 (highest). "
                "Write a short suggested_reply, or write 'no_reply' if no reply is needed."
            ),
            feedback="New episode started. Triage the email above.",
            score=0.0,
            done=False,
            reward=0.0,
        )

    def step(self, action: EmailTriageAction) -> EmailTriageObservation:
        self._state.step_count += 1
        task = self._current_task
        score = self._grade_action(action, task)

        current_idx = DIFFICULTY_LEVELS.index(self._difficulty)
        done = current_idx >= len(DIFFICULTY_LEVELS) - 1

        if not done:
            next_difficulty = DIFFICULTY_LEVELS[current_idx + 1]
            self._difficulty = next_difficulty
            self._current_task = random.choice(TASKS[next_difficulty])
            feedback = f"Score: {score:.2f}. Next task is {next_difficulty} difficulty."
            next_obs = self._current_task
        else:
            feedback = f"Final score: {score:.2f}. Episode complete!"
            next_obs = task

        return EmailTriageObservation(
            email_subject=next_obs["email_subject"],
            email_body=next_obs["email_body"],
            sender=next_obs["sender"],
            task_description=(
                "Triage this email. Classify it as one of: spam, urgent, normal, newsletter. "
                "Set a priority from 1 (lowest) to 5 (highest). "
                "Write a short suggested_reply, or write 'no_reply' if no reply is needed."
            ),
            feedback=feedback,
            score=score,
            done=done,
            reward=score,
        )

    @property
    def state(self) -> State:
        return self._state

    def _grade_action(self, action: EmailTriageAction, task: dict) -> float:
        score = 0.0

        # Classification worth 0.5
        if action.classification.lower() == task["correct_classification"]:
            score += 0.5

        # Priority worth 0.3 — full credit if exact, half if within 1
        correct_p = task["correct_priority"]
        given_p = max(1, min(5, action.priority))
        diff = abs(given_p - correct_p)
        if diff == 0:
            score += 0.3
        elif diff == 1:
            score += 0.15

        # Reply quality worth 0.2
        needs_reply = task.get("needs_reply", False)
        gave_reply = action.suggested_reply.lower() != "no_reply" and len(action.suggested_reply) > 5

        if needs_reply and gave_reply:
            score += 0.1
            required_keywords = task.get("required_reply_keywords", [])
            if required_keywords:
                reply_lower = action.suggested_reply.lower()
                matched = sum(1 for kw in required_keywords if kw in reply_lower)
                score += 0.1 * (matched / len(required_keywords))
            else:
                score += 0.1
        elif not needs_reply and not gave_reply:
            score += 0.2

        return round(min(score, 1.0), 2)