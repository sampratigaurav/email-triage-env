from typing import Optional, Dict
from pydantic import Field
from openenv.core.env_server.types import Action, Observation


class EmailTriageAction(Action):
    """The AI's response to an email triage task."""
    classification: str = Field(..., description="Classify as: spam, urgent, normal, or newsletter")
    priority: int = Field(..., description="Priority score 1-5 where 5 is highest priority")
    suggested_reply: str = Field(..., description="A short suggested reply or 'no_reply' if none needed")


class EmailTriageObservation(Observation):
    """What the AI sees — the email to triage."""
    email_subject: str = Field(..., description="Subject line of the email")
    email_body: str = Field(..., description="Body text of the email")
    sender: str = Field(..., description="Sender email address")
    task_description: str = Field(..., description="Instructions for the agent")
    feedback: str = Field(default="", description="Feedback after a step")
    score: float = Field(default=0.0, description="Score for the last action (0.0 to 1.0)")
    reward: float = Field(default=0.0, description="Reward for the last action (0.0 to 1.0)")
    done: bool = Field(default=False, description="Whether the episode is complete")
    reward_breakdown: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Breakdown of reward components: "
            "classification (0.0-0.5), priority (0.0-0.3), reply_quality (0.0-0.2)"
        )
    )