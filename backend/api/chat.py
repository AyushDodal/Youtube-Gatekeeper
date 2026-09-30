import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.agents.gatekeeper import InvalidLLMResponse
from backend.api.status import limits
from backend.llm.base import ProviderUnavailable
from backend.tools.registry import TOOL_DEFINITIONS

router = APIRouter(prefix="/api", tags=["gatekeeper"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("message")
    @classmethod
    def nonblank_message(cls, value):
        if not value.strip():
            raise ValueError("Please enter a message.")
        return value.strip()


def _complete(state, conversation_id, response, decision, status, events, *, user_message):
    state.db.add_message(conversation_id, "user", user_message)
    state.db.add_message(conversation_id, "assistant", response)
    if decision in {"grant", "deny"}:
        state.db.close_conversation(conversation_id)
    return {"response": response, "decision": decision, "conversation_id": conversation_id,
            "youtube_status": status, "tool_events": events}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    try:
        conversation = request.app.state.db.get_or_create_conversation(conversation_id)
    except (KeyError, ValueError):
        raise HTTPException(404, "Conversation not found.")
    return {**conversation, "messages": request.app.state.db.get_messages(conversation_id)}


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    state = request.app.state
    # One in-flight negotiation avoids duplicate model grants from multiple tabs.
    # The expiry task has its own execution path and keeps running during inference.
    async with state.chat_lock:
        try:
            conversation = state.db.get_or_create_conversation(payload.conversation_id)
        except (KeyError, ValueError):
            raise HTTPException(404, "Conversation not found. Start a new request.")
        conversation_id = conversation["id"]
        if conversation.get("status") == "closed":
            raise HTTPException(409, "This conversation has ended. Start a new request.")
        messages = state.db.get_messages(conversation_id)
        # Failed inference keeps the draft retryable without duplicated turns.
        messages.append({"role": "user", "content": payload.message})
        round_number = sum(row["role"] == "user" for row in messages)
        status = await asyncio.to_thread(state.tools.execute, "check_youtube_status")
        events = [{"name": "check_youtube_status", "status": "success", "detail": "Checked current access and expiry."}]
        if status.get("error"):
            return JSONResponse(status_code=503, content={"detail": status["error"], "conversation_id": conversation_id, "youtube_status": status})
        if status.get("session") is not None:
            return _complete(state, conversation_id,
                             "You already have an active session. Use the time you have; I won't extend it.",
                             "deny", status, events, user_message=payload.message)
        if round_number > state.settings.gatekeeper.max_question_rounds:
            return _complete(state, conversation_id,
                             "This request has reached the question limit. Access is denied. Start a new request with a specific purpose and time limit.",
                             "deny", status, events, user_message=payload.message)
        usage = await asyncio.to_thread(state.sessions.usage)
        context = {"youtube_status": status, "usage": {key: value for key, value in usage.items() if key not in {"history", "daily"}},
                   "limits": limits(state.settings), "round": round_number, "available_tools": TOOL_DEFINITIONS}
        try:
            decision = await state.agent.decide(messages, context)
        except (ProviderUnavailable, InvalidLLMResponse) as exc:
            return JSONResponse(status_code=503 if isinstance(exc, ProviderUnavailable) else 502,
                                content={"detail": str(exc), "conversation_id": conversation_id,
                                         "youtube_status": await asyncio.to_thread(state.sessions.status)})
        if decision.decision == "grant":
            try:
                session = await asyncio.to_thread(state.tools.execute, "grant_youtube_access",
                                                 duration_minutes=decision.requested_duration_minutes,
                                                 reason=decision.reasoning_summary,
                                                 conversation_id=conversation_id, conversation=messages)
                events.append({"name": "grant_youtube_access", "status": "success",
                               "detail": f"Approved {session['duration_minutes']} minutes; expiry is enforced by the backend."})
            except ValueError as exc:
                events.append({"name": "grant_youtube_access", "status": "rejected", "detail": str(exc)})
                return _complete(state, conversation_id, f"I can't approve that request: {exc}", "deny",
                                 await asyncio.to_thread(state.sessions.status), events, user_message=payload.message)
            except RuntimeError as exc:
                return JSONResponse(status_code=503, content={"detail": str(exc), "conversation_id": conversation_id,
                                                             "youtube_status": await asyncio.to_thread(state.sessions.status)})
        elif decision.decision == "deny":
            state.tools.execute("deny_youtube_access", reason=decision.reasoning_summary)
            events.append({"name": "deny_youtube_access", "status": "success", "detail": decision.reasoning_summary})
        return _complete(state, conversation_id, decision.response, decision.decision,
                         await asyncio.to_thread(state.sessions.status), events, user_message=payload.message)


@router.post("/admin/block")
async def block_now(request: Request):
    # If inference is in flight, apply the user's block after its final action.
    async with request.app.state.chat_lock:
        try:
            await asyncio.to_thread(request.app.state.sessions.block)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))
        return await asyncio.to_thread(request.app.state.sessions.status)
