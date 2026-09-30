from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

from backend.config import Settings
from backend.db.database import Database
from backend.services.policy_engine import PolicyViolation
from backend.services.session_manager import SessionManager
from backend.services.youtube_controller import ControllerError, END_MARKER, START_MARKER, YouTubeController


REASON = "Watch one Python cancellation tutorial for a current project."
CONVERSATION = [{"role": "user", "content": REASON}]


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 26, 12, 0).astimezone().astimezone(timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, *, minutes=0, seconds=0):
        self.now += timedelta(minutes=minutes, seconds=seconds)


@pytest.fixture
def harness(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_bytes(b"127.0.0.1 localhost\r\n192.168.1.10 private.internal\r\n")
    settings = Settings(database_path=tmp_path / "state.sqlite3", hosts_path=hosts, dry_run=True)
    clock = Clock()
    db = Database(settings.database_path)
    controller = YouTubeController(hosts, dry_run=True)
    manager = SessionManager(db, controller, settings, clock=clock)
    state = SimpleNamespace(db=db, controller=controller, manager=manager, settings=settings, clock=clock)
    state.conversation_id = db.get_or_create_conversation()["id"]
    yield state
    state.db.close()


def restart(harness):
    harness.db.close()
    harness.db = Database(harness.settings.database_path)
    harness.controller = YouTubeController(harness.settings.hosts_path, dry_run=True)
    harness.manager = SessionManager(harness.db, harness.controller, harness.settings, clock=harness.clock)
    harness.manager.restore()


def grant(harness, minutes=20):
    return harness.manager.grant(minutes, REASON, harness.conversation_id, CONVERSATION)


def test_default_startup_blocks_youtube(harness):
    harness.manager.restore()
    assert harness.controller.is_youtube_blocked()
    assert harness.manager.status()["expires_at"] is None
    assert harness.db.active_session() is None
    assert harness.manager.error is None


def test_every_grant_is_persisted_with_exact_expiry(harness):
    session = grant(harness)
    assert not harness.controller.is_youtube_blocked()
    saved = harness.db.active_session()
    assert saved["id"] == session["id"]
    assert datetime.fromisoformat(saved["started_at"]) == harness.clock.now
    assert datetime.fromisoformat(saved["expires_at"]) == harness.clock.now + timedelta(minutes=20)
    assert saved["reason"] == REASON
    assert saved["duration_minutes"] == 20
    assert harness.manager.status()["expires_at"] == saved["expires_at"]


def test_expired_session_automatically_blocks_and_logs_once(harness):
    grant(harness)
    harness.clock.advance(minutes=20)
    harness.manager.tick()
    assert harness.controller.is_youtube_blocked()
    assert harness.db.active_session() is None
    assert harness.db.sessions()[0]["status"] == "expired"
    assert harness.manager.usage()["today_minutes"] == pytest.approx(20)
    harness.manager.tick()
    rows = harness.db.connection.execute("SELECT * FROM usage_log").fetchall()
    assert len(rows) == 1
    assert rows[0]["duration_minutes"] == pytest.approx(20)


def test_active_session_survives_restart_without_extending_expiry(harness):
    session = grant(harness)
    harness.clock.advance(minutes=7)
    restart(harness)
    assert not harness.controller.is_youtube_blocked()
    assert harness.db.active_session()["expires_at"] == session["expires_at"]
    assert harness.manager.status()["expires_at"] == session["expires_at"]
    harness.clock.advance(minutes=13)
    harness.manager.tick()
    assert harness.controller.is_youtube_blocked()
    assert harness.db.active_session() is None


def test_expired_session_after_restart_is_immediately_blocked(harness):
    grant(harness)
    harness.clock.advance(minutes=45)
    restart(harness)
    assert harness.controller.is_youtube_blocked()
    assert harness.db.active_session() is None
    assert harness.db.sessions()[0]["status"] == "expired"
    assert harness.manager.usage()["today_minutes"] == pytest.approx(20)


def test_partial_managed_block_is_removed_when_restoring_active_session(harness):
    session = grant(harness)
    original = harness.controller.hosts_path.read_bytes()
    harness.controller.hosts_path.write_bytes(original + START_MARKER + b"\r\n127.0.0.1 youtube.com\r\n" + END_MARKER + b"\r\n")
    harness.clock.advance(minutes=5)
    restart(harness)
    assert harness.controller.hosts_path.read_bytes() == original
    assert harness.db.active_session()["expires_at"] == session["expires_at"]


def test_failed_unblock_never_returns_a_successful_grant(harness, monkeypatch):
    def fail_unlock(duration_minutes):
        raise ControllerError("Permission denied during unlock")

    monkeypatch.setattr(harness.controller, "unblock_youtube", fail_unlock)
    with pytest.raises(ControllerError, match="Permission denied"):
        grant(harness)
    assert harness.controller.is_youtube_blocked()
    assert harness.db.active_session() is None
    assert harness.db.sessions()[0]["status"] == "failed"
    assert harness.manager.usage()["today_minutes"] == 0
    assert harness.db.connection.execute("SELECT COUNT(*) FROM usage_log").fetchone()[0] == 0


def test_failed_expiry_block_is_visible_and_retried(harness, monkeypatch):
    grant(harness)
    harness.clock.advance(minutes=20)

    def fail_block():
        raise ControllerError("Hosts file is locked")

    with monkeypatch.context() as patch:
        patch.setattr(harness.controller, "block_youtube", fail_block)
        harness.manager.tick()
        assert harness.db.active_session() is not None
        assert "locked" in harness.manager.status()["error"]
        assert not harness.manager.status()["blocked"]
    harness.manager.tick()
    assert harness.db.active_session() is None
    assert harness.controller.is_youtube_blocked()
    assert harness.manager.error is None


def test_early_end_counts_only_elapsed_minutes(harness):
    grant(harness, 30)
    harness.clock.advance(minutes=7, seconds=30)
    assert harness.manager.usage()["today_minutes"] == pytest.approx(7.5)
    harness.manager.block()
    harness.clock.advance(minutes=50)
    usage = harness.manager.usage()
    assert usage["today_minutes"] == pytest.approx(7.5)
    assert usage["history"][0]["status"] == "ended"
    assert usage["remaining_minutes"] == pytest.approx(112.5)


def test_daily_limit_uses_actual_early_end_usage(harness):
    harness.settings.youtube.daily_limit_minutes = 30
    grant(harness, 20)
    harness.clock.advance(minutes=7, seconds=30)
    harness.manager.block()
    with pytest.raises(PolicyViolation, match="daily"):
        grant(harness, 25)
    assert harness.db.active_session() is None
    grant(harness, 20)
    assert harness.db.active_session() is not None


def test_usage_is_split_at_local_midnight(harness):
    harness.clock.now = datetime(2026, 9, 26, 23, 50).astimezone().astimezone(timezone.utc)
    grant(harness, 20)
    harness.clock.advance(minutes=15)
    usage = harness.manager.usage()
    assert usage["today_minutes"] == pytest.approx(5)
    assert usage["daily"][-2] == {"date": "2026-09-26", "minutes": pytest.approx(10)}
    assert usage["daily"][-1] == {"date": "2026-09-27", "minutes": pytest.approx(5)}
    harness.clock.advance(minutes=5)
    harness.manager.tick()
    assert harness.manager.usage()["today_minutes"] == pytest.approx(10)


def test_active_session_cannot_be_extended(harness):
    session = grant(harness)
    harness.clock.advance(minutes=5)
    with pytest.raises(PolicyViolation, match="already active"):
        grant(harness)
    assert harness.db.active_session()["expires_at"] == session["expires_at"]
    assert len(harness.db.sessions()) == 1


def test_missing_reason_never_changes_hosts_or_creates_session(harness):
    harness.manager.restore()
    original = harness.controller.hosts_path.read_bytes()
    with pytest.raises(PolicyViolation, match="reason"):
        harness.manager.grant(20, "  ", harness.conversation_id, CONVERSATION)
    assert harness.controller.hosts_path.read_bytes() == original
    assert harness.db.sessions() == []


@pytest.mark.parametrize("database_error", [
    sqlite3.DatabaseError("database disk image is malformed"),
    sqlite3.OperationalError("database is locked"),
])
def test_unreadable_session_state_blocks_existing_access_and_reports_error(harness, monkeypatch, database_error):
    session = grant(harness)
    assert not harness.controller.is_youtube_blocked()

    def fail_read():
        raise database_error

    with monkeypatch.context() as patch:
        patch.setattr(harness.db, "active_session", fail_read)
        harness.manager.tick()
        status = harness.manager.status()
        assert status["blocked"] is True
        assert status["session"] is None
        assert status["expires_at"] is None
        assert "state" in status["error"].lower()
        with pytest.raises(ControllerError, match="state"):
            grant(harness)
    # A transient read failure does not invent a fresh grant or a later expiry.
    harness.clock.advance(minutes=3)
    harness.manager.tick()
    assert harness.manager.error is None
    assert not harness.controller.is_youtube_blocked()
    assert harness.db.active_session()["expires_at"] == session["expires_at"]
    assert len(harness.db.sessions()) == 1


def test_database_recovery_after_deadline_keeps_youtube_blocked(harness, monkeypatch):
    grant(harness)

    def fail_read():
        raise sqlite3.OperationalError("database read failed")

    with monkeypatch.context() as patch:
        patch.setattr(harness.db, "active_session", fail_read)
        harness.manager.tick()
        assert harness.controller.is_youtube_blocked()
        harness.clock.advance(minutes=25)
    harness.manager.tick()
    assert harness.controller.is_youtube_blocked()
    assert harness.db.active_session() is None
    assert harness.db.sessions()[0]["status"] == "expired"
    assert harness.manager.error is None


def test_database_and_recovery_permission_failure_are_both_visible(harness, monkeypatch):
    grant(harness)

    def fail_read():
        raise sqlite3.DatabaseError("database disk image is malformed")

    def fail_block():
        raise ControllerError("Permission denied: recovery requires Administrator privileges.")

    with monkeypatch.context() as patch:
        patch.setattr(harness.db, "active_session", fail_read)
        patch.setattr(harness.controller, "block_youtube", fail_block)
        harness.manager.tick()
        assert "Administrator" in harness.manager.error
        status = harness.manager.status()
        assert status["blocked"] is False
        assert status["expires_at"] is None
        assert "state" in status["error"].lower()
        assert "Administrator" in status["error"]
    harness.clock.advance(minutes=20)
    harness.manager.tick()
    assert harness.controller.is_youtube_blocked()
    assert harness.manager.error is None


def test_failed_database_expiry_commit_stays_blocked_and_retries(harness, monkeypatch):
    grant(harness)
    harness.clock.advance(minutes=20)

    def fail_finish(*args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error")

    with monkeypatch.context() as patch:
        patch.setattr(harness.db, "finish_session", fail_finish)
        harness.manager.tick()
        assert harness.controller.is_youtube_blocked()
        assert harness.db.active_session() is not None
        assert "save session state" in harness.manager.status()["error"]
    harness.manager.tick()
    assert harness.controller.is_youtube_blocked()
    assert harness.db.active_session() is None
    assert harness.manager.usage()["today_minutes"] == pytest.approx(20)
    assert harness.manager.error is None
