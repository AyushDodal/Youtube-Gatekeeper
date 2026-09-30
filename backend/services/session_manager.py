"""Persist grants before unblocking, reconcile on restart, and expire independently of chat."""
import logging
import sqlite3
from datetime import datetime, timedelta, time, timezone
from threading import RLock

from backend.config import Settings
from backend.db.database import Database, utcnow
from backend.services.policy_engine import PolicyEngine, PolicyViolation
from backend.services.youtube_controller import YouTubeController, ControllerError

logger = logging.getLogger(__name__)


class SessionManager:
    def __init__(self, db: Database, controller: YouTubeController, settings: Settings, *, clock=utcnow):
        self.db = db
        self.controller = controller
        self.settings = settings
        self.policy = PolicyEngine(settings.youtube)
        self.clock = clock
        self.lock = RLock()
        self.error: str | None = None

    def restore(self):
        self.tick()

    def tick(self):
        with self.lock:
            try:
                session = self.db.active_session()
                now = self.clock()
                if session and datetime.fromisoformat(session["expires_at"]) > now:
                    # Remove even partially edited sections; idempotent writes skip DNS flushes.
                    # The persisted exact expiry, not the controller's informational expiry, is authoritative.
                    self.controller.unblock_youtube(session["duration_minutes"])
                else:
                    self.controller.block_youtube()
                    if session:
                        self.db.finish_session(session, "expired", datetime.fromisoformat(session["expires_at"]))
                self.error = None
            except sqlite3.Error as exc:
                self.error = "Cannot read or save session state. YouTube is being blocked; check the local database."
                logger.error("Session database failed: %s", exc)
                try:
                    self.controller.block_youtube()
                except (ControllerError, OSError) as block_error:
                    self.error += " " + str(block_error)
            except (ControllerError, OSError) as exc:
                self.error = str(exc)
                logger.error("Unable to enforce YouTube state: %s", exc)

    def status(self) -> dict:
        with self.lock:
            try:
                session = self.db.active_session()
            except sqlite3.Error:
                session = None
                self.error = self.error or "Cannot read session state. Check the local SQLite database."
            try:
                blocked = self.controller.is_youtube_blocked()
            except (ControllerError, OSError) as exc:
                self.error = str(exc)
                blocked = False  # Never claim protection when the hosts file cannot be inspected.
            expiry = session["expires_at"] if session else None
            return {"blocked": blocked, "expires_at": expiry, "session": session,
                    "error": self.error or getattr(self.controller, "warning", None),
                    "dry_run": self.settings.dry_run}

    def grant(self, duration_minutes, reason, conversation_id: str, conversation: list[dict]) -> dict:
        with self.lock:
            self.tick()
            if self.error:
                raise ControllerError(self.error)
            if self.db.active_session():
                raise PolicyViolation("A session is already active. It cannot be extended; finish it first.")
            self.policy.validate_access_request(duration_minutes, reason, conversation, used_minutes=self.usage()["today_minutes"])
            now = self.clock()
            # FULL SQLite commit comes first: a crash can never leave an untracked unlock.
            session = self.db.create_session(conversation_id=conversation_id, reason=reason.strip(), started_at=now,
                                             expires_at=now + timedelta(minutes=duration_minutes), duration_minutes=duration_minutes)
            try:
                self.controller.unblock_youtube(duration_minutes)
            except (ControllerError, OSError) as exc:
                self.db.finish_session(session, "failed", now)
                self.error = str(exc)
                try:
                    self.controller.block_youtube()
                except (ControllerError, OSError):
                    logger.exception("Could not restore block after failed unlock")
                raise ControllerError(str(exc)) from exc
            return session

    def block(self):
        with self.lock:
            try:
                self.controller.block_youtube()
                session = self.db.active_session()
                if session:
                    self.db.finish_session(session, "ended", self.clock())
                self.error = None
            except (ControllerError, OSError, sqlite3.Error) as exc:
                self.error = str(exc)
                raise ControllerError(str(exc)) from exc

    def _minutes_between(self, start: datetime, end: datetime) -> float:
        total = 0.0
        now = self.clock()
        for session in self.db.sessions():
            if session["status"] == "failed":
                continue
            session_start = datetime.fromisoformat(session["started_at"])
            session_end = datetime.fromisoformat(session["ended_at"] or session["expires_at"])
            total += max(0, (min(session_end, end, now) - max(session_start, start)).total_seconds()) / 60
        return total

    def usage(self) -> dict:
        with self.lock:
            today = self.clock().astimezone().date()
            daily = []
            for offset in range(6, -1, -1):
                day = today - timedelta(days=offset)
                start = datetime.combine(day, time.min).astimezone().astimezone(timezone.utc)
                end = datetime.combine(day + timedelta(days=1), time.min).astimezone().astimezone(timezone.utc)
                daily.append({"date": day.isoformat(), "minutes": self._minutes_between(start, end)})
            used = daily[-1]["minutes"]
            return {"today_minutes": used, "daily_limit_minutes": self.settings.youtube.daily_limit_minutes,
                    "remaining_minutes": max(0, self.settings.youtube.daily_limit_minutes - used),
                    "history": self.db.sessions(limit=100), "daily": daily}
