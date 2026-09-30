import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["status"])


def limits(settings):
    return {**settings.youtube.model_dump(), "max_question_rounds": settings.gatekeeper.max_question_rounds}


@router.get("/status")
async def get_status(request: Request):
    state = request.app.state
    status, model = await asyncio.gather(asyncio.to_thread(state.sessions.status), state.provider.health())
    return {**status, "model": model, "limits": limits(state.settings),
            "server_time": datetime.now(timezone.utc).isoformat()}


@router.get("/session")
async def get_session(request: Request):
    return await asyncio.to_thread(request.app.state.sessions.status)
