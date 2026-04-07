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
            "email_body": "I placed order #8823 two weeks ago and it still hasn't arrived. This is unacceptable. I need an update immediately.",
            "sender": "angry.customer@gmail.com",
            "correct_classification": "urgent",
            "correct_priority": 4,
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
        {
            "email_subject": "Security breach detected - immediate response needed",
            "email_body": "Our monitoring system detected unauthorized access to the customer database at 03:14 UTC. Approximately 50,000 records may be compromised. Legal and PR teams have been notified. We need your authorization to take the system offline and begin incident response protocol.",
            "sender": "security@company.com",
            "correct_classification": "urgent",
            "correct_priority": 5,
            "needs_reply": True,
            "required_reply_keywords": ["authorize", "offline", "confirm"],
        },
        {
            "email_subject": "Budget approval needed for Q3 marketing campaign",
            "email_body": "Hi, the Q3 campaign proposal is attached. We need budget approval of $45,000 by end of week to secure vendor slots. The campaign targets 200,000 users and projected ROI is 340%. Please review and approve or suggest amendments.",
            "sender": "marketing.director@company.com",
            "correct_classification": "urgent",
            "correct_priority": 4,
            "needs_reply": True,
            "required_reply_keywords": ["approve", "budget", "confirm"],
        },
        {
            "email_subject": "Fwd: Fwd: Fwd: Funny cat video",
            "email_body": "Haha you have to see this! [forwarded 4 times] Original message: check out this hilarious compilation of cats falling off things.",
            "sender": "uncle.bob@hotmail.com",
            "correct_classification": "spam",
            "correct_priority": 1,
            "needs_reply": False,
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

    # 1. Classification — worth 0.5
    given_class = action.classification.lower().strip()
    correct_class = task["correct_classification"]

    if given_class == correct_class:
        score += 0.5
    else:
        # Partial credit for related misclassifications
        # urgent/normal are closer than spam/newsletter
        partial_credit_pairs = [
            ("urgent", "normal"),
            ("normal", "urgent"),
        ]
        if (given_class, correct_class) in partial_credit_pairs:
            score += 0.15

    # 2. Priority — worth 0.3
    correct_p = task["correct_priority"]
    try:
        given_p = max(1, min(5, int(action.priority)))
    except (ValueError, TypeError):
        given_p = 3  # default if invalid

    diff = abs(given_p - correct_p)
    if diff == 0:
        score += 0.3
    elif diff == 1:
        score += 0.2
    elif diff == 2:
        score += 0.1
    # diff 3+ gets nothing

    # 3. Reply quality — worth 0.2
    needs_reply = task.get("needs_reply", False)
    reply = action.suggested_reply.strip()
    gave_reply = reply.lower() != "no_reply" and len(reply) > 5

    if needs_reply and gave_reply:
        score += 0.1  # base credit for attempting

        # Check reply length — too short replies get less credit
        if len(reply) > 20:
            score += 0.05

        # Check for required keywords
        required_keywords = task.get("required_reply_keywords", [])
        if required_keywords:
            reply_lower = reply.lower()
            matched = sum(1 for kw in required_keywords if kw in reply_lower)
            keyword_score = 0.05 * (matched / len(required_keywords))
            score += keyword_score
        else:
            score += 0.05  # full reply credit for non-keyword tasks

    elif not needs_reply and not gave_reply:
        score += 0.2  # correctly identified no reply needed

    elif not needs_reply and gave_reply:
        score += 0.05  # small credit — at least they tried

    return round(min(score, 1.0), 2)