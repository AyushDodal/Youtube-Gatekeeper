import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import threading
import time

from fastapi.testclient import TestClient
import pytest

from backend.config import GatekeeperPolicy, Settings
from backend.db.database import Database
from backend.llm.base import LLMProvider, ProviderUnavailable
from backend.main import create_app
from backend.services.youtube_controller import PermissionDeniedError, YouTubeController


def model_response(decision="continue_questioning", duration=None):
    return json.dumps({"response": "What specific outcome are you working toward?" if decision == "continue_questioning" else "A bounded tutorial session is reasonable.",
                       "decision": decision, "requested_duration_minutes": duration,
                       "reasoning_summary": "Learn Python generators through a specific tutorial."})


class MockProvider(LLMProvider):
    def __init__(self, *responses):
        self.responses = list(responses or [model_response()])
        self.calls = 0

    async def generate(self, messages, schema):
        self.calls += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def application(tmp_path):
    def factory(provider=None, rounds=8, controller=None):
        hosts = tmp_path / "hosts"
        hosts.write_text("# unrelated hosts entry\n127.0.0.1 my-local-site.test\n", encoding="utf-8")
        settings = Settings(database_path=tmp_path / "gatekeeper.sqlite3", hosts_path=hosts,
                            gatekeeper=GatekeeperPolicy(max_question_rounds=rounds), poll_interval_seconds=0.05)
        return create_app(settings=settings, provider=provider or MockProvider(), controller=controller)
    return factory


def client(app):
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_status_session_usage_and_restore_conversation(application):
    with client(application()) as browser:
        status = browser.get("/api/status").json()
        assert status["blocked"] is True
        assert status["expires_at"] is None
        assert status["model"]["available"] is True
        assert status["limits"]["max_session_minutes"] == 60
        assert datetime.fromisoformat(status["server_time"]).tzinfo is not None
        assert browser.get("/api/session").json()["session"] is None
        assert browser.get("/api/usage").json()["today_minutes"] == 0
        response = browser.post("/api/chat", json={"message": "I need YouTube"})
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "continue_questioning"
        conversation = browser.get(f"/api/conversations/{data['conversation_id']}").json()
        assert [row["role"] for row in conversation["messages"]] == ["user", "assistant"]
        assert conversation["status"] == "open"


@pytest.mark.parametrize("proposed_minutes", [15, 5000])
def test_question_with_proposed_duration_cannot_unlock(application, proposed_minutes):
    with client(application(MockProvider(model_response("continue_questioning", proposed_minutes)))) as browser:
        result = browser.post("/api/chat", json={"message": "I want a tutorial for 15 minutes."})
        assert result.status_code == 200
        assert result.json()["decision"] == "continue_questioning"
        assert result.json()["youtube_status"]["blocked"]
        assert browser.get("/api/session").json()["session"] is None


def test_only_model_plus_policy_can_grant_and_active_session_cannot_renew(application):
    provider = MockProvider(model_response("grant", 20))
    app = application(provider)
    with client(app) as browser:
        data = browser.post("/api/chat", json={"message": "20 minutes to study Python generators with a tutorial."}).json()
        assert data["decision"] == "grant"
        assert data["youtube_status"]["blocked"] is False
        expiry = data["youtube_status"]["expires_at"]
        assert expiry
        assert data["tool_events"][-1]["name"] == "grant_youtube_access"
        assert browser.post("/api/chat", json={"message": "more please", "conversation_id": data["conversation_id"]}).status_code == 409
        another = browser.post("/api/chat", json={"message": "Extend it by an hour"}).json()
        assert another["decision"] == "deny"
        assert another["youtube_status"]["expires_at"] == expiry
        assert provider.calls == 1
        assert browser.post("/api/grant", json={"duration_minutes": 20}).status_code in {404, 405}
        assert browser.post("/api/admin/block", json={}).json()["blocked"] is True
        history = browser.get("/api/usage").json()["history"]
        assert history[0]["status"] == "ended"


@pytest.mark.parametrize("duration", [1, 61, 5000, -1, 0])
def test_bad_llm_duration_is_rejected_by_policy(application, duration):
    with client(application(MockProvider(model_response("grant", duration)))) as browser:
        response = browser.post("/api/chat", json={"message": "Study generators with a video."})
        assert response.status_code == 200
        assert response.json()["decision"] == "deny"
        assert response.json()["youtube_status"]["blocked"] is True
        assert response.json()["tool_events"][-1]["status"] == "rejected"
        assert browser.get("/api/usage").json()["history"] == []


@pytest.mark.parametrize("bad_response", ["{broken}", model_response("grant", True), model_response("grant", "20")])
def test_malformed_model_output_leaves_hosts_blocked_and_retry_has_no_duplicate_turn(application, bad_response):
    provider = MockProvider(bad_response, model_response())
    with client(application(provider)) as browser:
        response = browser.post("/api/chat", json={"message": "I need a tutorial"})
        assert response.status_code == 502
        conversation_id = response.json()["conversation_id"]
        assert browser.get(f"/api/conversations/{conversation_id}").json()["messages"] == []
        assert browser.get("/api/status").json()["blocked"] is True
        retry = browser.post("/api/chat", json={"message": "I need a tutorial", "conversation_id": conversation_id})
        assert retry.status_code == 200
        assert len(browser.get(f"/api/conversations/{conversation_id}").json()["messages"]) == 2


def test_offline_model_reports_clear_error_without_grant(application):
    with client(application(MockProvider(ProviderUnavailable("Start Ollama and retry.")))) as browser:
        response = browser.post("/api/chat", json={"message": "Need a video"})
        assert response.status_code == 503
        assert "Start Ollama" in response.json()["detail"]
        assert response.json()["youtube_status"]["blocked"] is True


def test_question_round_limit_is_enforced_by_backend(application):
    provider = MockProvider(model_response(), model_response())
    with client(application(provider, rounds=2)) as browser:
        first = browser.post("/api/chat", json={"message": "Need YouTube"}).json()
        second = browser.post("/api/chat", json={"message": "Just because", "conversation_id": first["conversation_id"]}).json()
        assert second["decision"] == "deny"
        assert "question limit" in second["response"]
        assert browser.get(f"/api/conversations/{first['conversation_id']}").json()["status"] == "closed"


@pytest.mark.parametrize("payload", [{"message": " "}, {"message": 12}, {"message": "x" * 4001},
                                      {"message": "please", "duration_minutes": 20}, {"message": "please", "role": "system"}])
def test_frontend_input_is_validated(application, payload):
    with client(application()) as browser:
        assert browser.post("/api/chat", json=payload).status_code == 422


def test_local_browser_boundary_rejects_remote_origins_hosts_and_form_requests(application):
    with client(application()) as browser:
        assert browser.post("/api/admin/block", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
        assert browser.get("/api/status", headers={"Host": "evil.example"}).status_code == 400
        assert browser.post("/api/admin/block", content="anything", headers={"Content-Type": "text/plain"}).status_code == 415
        assert browser.post("/api/admin/block", json={}, headers={"Origin": "http://localhost:5173"}).status_code == 200
        assert browser.get("/api/conversations/unknown").status_code == 404


def test_permission_error_keeps_status_accessible_and_does_not_claim_blocking(application, tmp_path):
    class DeniedController(YouTubeController):
        def block_youtube(self):
            raise PermissionDeniedError("Administrator privileges are required.")

    hosts = tmp_path / "denied-hosts"
    hosts.write_text("", encoding="utf-8")
    provider = MockProvider()
    with client(application(provider, controller=DeniedController(hosts))) as browser:
        status = browser.get("/api/status").json()
        assert status["blocked"] is False
        assert "Administrator" in status["error"]
        assert browser.post("/api/chat", json={"message": "I need a video"}).status_code == 503
        assert provider.calls == 0


def test_graceful_shutdown_blocks_but_preserves_persisted_expiry(application):
    app = application(MockProvider(model_response("grant", 5)))
    with client(app) as browser:
        grant = browser.post("/api/chat", json={"message": "Five minutes to learn one Python concept."}).json()
        expiry = grant["youtube_status"]["expires_at"]
        assert app.state.controller.is_youtube_blocked() is False
        db_path = app.state.settings.database_path
    assert app.state.controller.is_youtube_blocked() is True
    database = Database(db_path)
    try:
        assert database.active_session()["expires_at"] == expiry
    finally:
        database.close()


def test_only_one_backend_can_own_the_same_database(application):
    first, second = application(), application()
    with client(first):
        with pytest.raises(RuntimeError, match="already running"):
            with client(second):
                pass
    # The OS lock is released after clean shutdown.
    with client(second) as browser:
        assert browser.get("/api/status").status_code == 200


def test_database_startup_failure_attempts_to_restore_blocking(application, tmp_path):
    app = application()
    (tmp_path / "gatekeeper.sqlite3").write_bytes(b"This is not a database")
    with pytest.raises(RuntimeError, match="Cannot open the local session database"):
        with client(app):
            pass
    assert app.state.controller.is_youtube_blocked()


def test_expiry_continues_while_local_model_is_waiting(application):
    entered, release = threading.Event(), threading.Event()

    class SlowProvider(LLMProvider):
        async def generate(self, messages, schema):
            entered.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
            return model_response("deny")

    app = application(SlowProvider())
    with client(app) as browser, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(browser.post, "/api/chat", json={"message": "I need a tutorial"})
        try:
            assert entered.wait(timeout=3)
            conversation = app.state.db.get_or_create_conversation()
            now = datetime.now(timezone.utc)
            app.state.sessions.clock = lambda: now
            app.state.sessions.grant(5, "Study Python", conversation["id"], [{"role": "user", "content": "Study Python"}])
            app.state.sessions.clock = lambda: now + timedelta(minutes=6)
            deadline = time.monotonic() + 3
            while app.state.db.active_session() is not None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert app.state.db.active_session() is None
            assert app.state.controller.is_youtube_blocked()
            assert not pending.done()
        finally:
            release.set()
        assert pending.result(timeout=3).status_code == 200
