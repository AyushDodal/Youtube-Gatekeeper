"""Run with: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000.

Use a single worker: one process owns the hosts controller and session scheduler.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.agents.gatekeeper import GatekeeperAgent
from backend.api import chat, status, usage
from backend.config import load_settings
from backend.db.database import Database
from backend.llm.ollama_provider import OllamaProvider
from backend.services.instance_lock import InstanceLock
from backend.services.session_manager import SessionManager
from backend.services.youtube_controller import YouTubeController
from backend.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)
LOCAL_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173",
                 "http://localhost:8000", "http://127.0.0.1:8000"}


class LocalRequestMiddleware:
    """Reject cross-origin mutations, remote peers, and browser form submissions."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode("latin1")
        peer = scope.get("client")
        if peer and peer[0] not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            response = JSONResponse({"detail": "This application only accepts local requests."}, status_code=403)
        elif origin and origin not in LOCAL_ORIGINS:
            response = JSONResponse({"detail": "This origin is not allowed."}, status_code=403)
        elif scope["method"] in {"POST", "PUT", "PATCH", "DELETE"} and headers.get(b"content-type", b"").split(b";")[0].strip().lower() != b"application/json":
            response = JSONResponse({"detail": "Mutating requests require Content-Type: application/json."}, status_code=415)
        else:
            return await self.app(scope, receive, send)
        await response(scope, receive, send)


async def _expiry_loop(app, stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(app.state.sessions.tick)
        except Exception:
            # A failed hosts write is retried on the next tick; never lose the task.
            logger.exception("Could not enforce the current YouTube session; will retry")
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=app.state.settings.poll_interval_seconds)


def create_app(settings=None, provider=None, controller=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        configured = settings if settings is not None else load_settings()
        app.state.settings = configured
        with InstanceLock(configured.database_path.with_suffix(".lock")):
            app.state.controller = controller if controller is not None else YouTubeController(hosts_path=configured.hosts_path, dry_run=configured.dry_run)
            try:
                app.state.db = Database(configured.database_path)
            except (sqlite3.Error, OSError) as exc:
                try:
                    await asyncio.to_thread(app.state.controller.block_youtube)
                except RuntimeError:
                    logger.exception("Could not block YouTube after a database startup failure")
                raise RuntimeError("Cannot open the local session database. YouTube blocking was attempted; repair or restore the database before restarting.") from exc
            app.state.provider = provider if provider is not None else OllamaProvider(configured.ollama_model, configured.ollama_base_url)
            try:
                app.state.sessions = SessionManager(app.state.db, app.state.controller, configured)
                app.state.tools = ToolRegistry(app.state.sessions)
                app.state.agent = GatekeeperAgent(app.state.provider)
                app.state.chat_lock = asyncio.Lock()
                try:
                    await asyncio.to_thread(app.state.sessions.restore)
                except RuntimeError:
                    logger.exception("Initial hosts enforcement failed; status remains available")
                stop = asyncio.Event()
                task = asyncio.create_task(_expiry_loop(app, stop), name="youtube-session-expiry")
                try:
                    yield
                finally:
                    # A cancellation cannot stop a to_thread worker. Signal and
                    # join it before reblocking, so no late tick can reopen access.
                    stop.set()
                    await task
                    # Preserve the DB deadline for a subsequent application restart.
                    try:
                        await asyncio.to_thread(app.state.controller.block_youtube)
                    except RuntimeError:
                        logger.exception("Could not restore blocking during shutdown")
            finally:
                await app.state.provider.close()
                app.state.db.close()

    app = FastAPI(title="YouTube Gatekeeper", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        logger.error("Local database request failed: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Cannot read or write the local database. Check available disk space and restore the database before retrying."})

    app.add_middleware(CORSMiddleware, allow_origins=sorted(LOCAL_ORIGINS), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.add_middleware(LocalRequestMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
    app.include_router(status.router)
    app.include_router(chat.router)
    app.include_router(usage.router)
    frontend = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
