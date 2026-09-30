"""Deterministic authority: model output is only a request, never permission."""
from backend.config import YouTubePolicy


class PolicyViolation(ValueError):
    pass


class PolicyEngine:
    def __init__(self, config: YouTubePolicy):
        self.config = config

    def validate_access_request(self, duration_minutes, reason, conversation, *, used_minutes: float = 0):
        if type(duration_minutes) is not int:
            raise PolicyViolation("Every grant needs a finite duration in whole minutes.")
        if duration_minutes < self.config.min_session_minutes:
            raise PolicyViolation(f"Sessions must be at least {self.config.min_session_minutes} minutes.")
        if duration_minutes > self.config.max_session_minutes:
            raise PolicyViolation(f"Sessions cannot exceed {self.config.max_session_minutes} minutes.")
        if not isinstance(reason, str) or not reason.strip():
            raise PolicyViolation("A specific reason is required before access can be granted.")
        if len(reason) > 2000:
            raise PolicyViolation("The access reason is too long.")
        if not any(m.get("role") == "user" and str(m.get("content", "")).strip() for m in conversation):
            raise PolicyViolation("Access must be requested through a conversation with the Gatekeeper.")
        if used_minutes + duration_minutes > self.config.daily_limit_minutes + 1e-9:
            raise PolicyViolation("That session would exceed your daily YouTube allowance.")


def validate_access_request(duration_minutes, reason, conversation, *, used_minutes=0, config=None):
    PolicyEngine(config or YouTubePolicy()).validate_access_request(duration_minutes, reason, conversation, used_minutes=used_minutes)
