"""Email Triage Environment Client."""

from typing import Dict
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import EmailTriageAction, EmailTriageObservation


class EmailTriageEnv(
    EnvClient[EmailTriageAction, EmailTriageObservation, State]
):
    """
    Client for the Email Triage Environment.

    Maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions across a full episode.

    Example:
        async with EmailTriageEnv(base_url="https://sampratigaurav-email-triage-env.hf.space") as env:
            result = await env.reset()
            print(result.observation.email_subject)

            action = EmailTriageAction(
                classification="spam",
                priority=1,
                suggested_reply="no_reply"
            )
            result = await env.step(action)
            print(result.reward)
    """

    def _step_payload(self, action: EmailTriageAction) -> Dict:
        return {
            "classification":  action.classification,
            "priority":        action.priority,
            "suggested_reply": action.suggested_reply,
        }

    def _parse_result(self, payload: Dict) -> StepResult[EmailTriageObservation]:
        obs_data = payload.get("observation", payload)
        observation = EmailTriageObservation(
            email_subject=obs_data.get("email_subject", ""),
            email_body=obs_data.get("email_body", ""),
            sender=obs_data.get("sender", ""),
            task_description=obs_data.get("task_description", ""),
            feedback=obs_data.get("feedback", ""),
            score=obs_data.get("score", 0.0),
            reward=obs_data.get("reward", 0.0),
            done=obs_data.get("done", False),
            reward_breakdown=obs_data.get("reward_breakdown"),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", obs_data.get("reward", 0.0)),
            done=payload.get("done", obs_data.get("done", False)),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )