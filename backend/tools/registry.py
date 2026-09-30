"""A fixed registry: names and handlers never come from user or model code."""

from types import MappingProxyType

from backend.tools import youtube_tools


TOOL_DEFINITIONS = (
    {"name": "check_youtube_status", "description": "Read actual YouTube blocking status and the current session expiry; does not change access."},
    {"name": "grant_youtube_access", "description": "Request temporary access with an integer duration and a reason. Backend policy validates limits, daily allowance and active sessions before changing hosts."},
    {"name": "deny_youtube_access", "description": "Record a denial with a reason. Does not grant, renew or extend access."},
)


class ToolRegistry:
    def __init__(self, sessions):
        self.sessions = sessions
        self._handlers = MappingProxyType({
            "check_youtube_status": lambda: youtube_tools.check_youtube_status(sessions),
            "grant_youtube_access": lambda **kwargs: youtube_tools.grant_youtube_access(sessions, **kwargs),
            "deny_youtube_access": youtube_tools.deny_youtube_access,
        })

    def execute(self, name: str, **arguments):
        if name not in self._handlers:
            raise ValueError("Unknown tool. Only the application's fixed tool registry is available.")
        return self._handlers[name](**arguments)
