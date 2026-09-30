import asyncio

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["usage"])


@router.get("/usage")
async def get_usage(request: Request):
    return await asyncio.to_thread(request.app.state.sessions.usage)
