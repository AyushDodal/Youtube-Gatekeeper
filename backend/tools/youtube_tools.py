"""Tool handlers call the policy-enforcing session service, never raw model code."""


def check_youtube_status(sessions):
    return sessions.status()


def grant_youtube_access(sessions, *, duration_minutes, reason, conversation_id, conversation):
    # SessionManager revalidates types, limits, usage and active-session state.
    return sessions.grant(duration_minutes, reason, conversation_id, conversation)


def deny_youtube_access(*, reason):
    return {"allowed": False, "reason": reason}
