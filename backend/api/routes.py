import json
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlite3 import IntegrityError

from backend.auth import clear_session, current_user, hash_password, set_session, verify_password
from backend.database.db import (
    clear_all_conversations,
    conversation_exists,
    create_conversation,
    create_user,
    delete_assistant_message,
    delete_conversation,
    create_document,
    delete_document,
    get_messages,
    get_user_by_email,
    list_conversations,
    list_documents,
    add_trace_event,
    list_trace_events,
    rename_conversation,
    save_message,
    update_default_title,
)
from backend.models import ChatRequest, ConversationCreate, ConversationRename
from backend.services.chat_service import build_context, retrieve_context, stream_ai_response
from backend.agent_tools import should_use_agent
from backend.governance import check_input_guardrails
from backend.evaluations import run_evaluations
from pydantic import BaseModel, Field

router = APIRouter()


class AuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


@router.post("/auth/register")
def register(payload: AuthRequest, response: Response):
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email address.")
    try:
        user = create_user(email, hash_password(payload.password))
    except IntegrityError:
        raise HTTPException(409, "An account with that email already exists.")
    set_session(response, user["id"])
    return {"id": user["id"], "email": user["email"]}


@router.post("/auth/login")
def login(payload: AuthRequest, response: Response):
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Email or password is incorrect.")
    set_session(response, user["id"])
    return {"id": user["id"], "email": user["email"]}


@router.post("/auth/logout")
def logout(response: Response):
    clear_session(response)
    return {"message": "Signed out."}


@router.get("/auth/me")
def me(request: Request):
    user = current_user(request)
    return {"id": user["id"], "email": user["email"]}


@router.get("/conversations")
def conversations(request: Request):
    return list_conversations(current_user(request)["id"])


@router.get("/documents")
def documents(request: Request):
    return list_documents(current_user(request)["id"])


@router.get("/traces")
def traces(request: Request, trace_id: str | None = None, limit: int = 100):
    user_id = current_user(request)["id"]
    return list_trace_events(user_id, trace_id=trace_id, limit=max(1, min(limit, 200)))


@router.get("/evaluations")
def evaluations(request: Request):
    current_user(request)
    return run_evaluations()


@router.post("/documents")
async def upload_document(request: Request, file: UploadFile = File(...)):
    user_id = current_user(request)["id"]
    filename = file.filename or "uploaded-document"
    if not filename.lower().endswith((".txt", ".md", ".pdf")):
        raise HTTPException(415, "Only TXT, Markdown, and PDF files are supported.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Files must be smaller than 5 MB.")
    if filename.lower().endswith(".pdf"):
        from io import BytesIO
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    else:
        text = data.decode("utf-8", errors="replace")
    chunks = [text[index:index + 1400].strip() for index in range(0, len(text), 1200)]
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        raise HTTPException(422, "The uploaded file did not contain readable text.")
    return create_document(user_id, filename, chunks)


@router.delete("/documents/{document_id}")
def remove_document(document_id: int, request: Request):
    if not delete_document(document_id, current_user(request)["id"]):
        raise HTTPException(404, "Document not found.")
    return {"message": "Document deleted."}


@router.post("/conversations")
def add_conversation(payload: ConversationCreate, request: Request):
    return create_conversation(current_user(request)["id"], payload.title)


@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: int, payload: ConversationRename, request: Request):
    user_id = current_user(request)["id"]
    if not conversation_exists(conversation_id, user_id):
        raise HTTPException(404, "Conversation not found.")
    return rename_conversation(conversation_id, user_id, payload.title)


@router.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: int, request: Request):
    user_id = current_user(request)["id"]
    if not conversation_exists(conversation_id, user_id):
        raise HTTPException(404, "Conversation not found.")
    delete_conversation(conversation_id, user_id)
    return {"message": "Conversation deleted."}


@router.delete("/conversations")
def remove_all_conversations(request: Request):
    clear_all_conversations(current_user(request)["id"])
    return {"message": "All conversations deleted."}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, request: Request):
    user_id = current_user(request)["id"]
    if not conversation_exists(conversation_id, user_id):
        raise HTTPException(404, "Conversation not found.")
    return get_messages(conversation_id, user_id)


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    user_id = current_user(request)["id"]
    message = payload.message.strip()
    if not message:
        raise HTTPException(400, "Message cannot be empty.")
    if not conversation_exists(payload.conversation_id, user_id):
        raise HTTPException(404, "Conversation not found.")

    trace_id = uuid.uuid4().hex
    trace_started = time.perf_counter()
    add_trace_event(trace_id, user_id, "request_started", payload.conversation_id,
                    details={"regenerate": payload.regenerate})
    allowed, guardrail_reason = check_input_guardrails(message)
    add_trace_event(trace_id, user_id, "guardrail_checked", payload.conversation_id,
                    success=allowed, details={"decision": "allow" if allowed else "block"})
    if not allowed:
        add_trace_event(trace_id, user_id, "request_blocked", payload.conversation_id,
                        success=False, details={"reason": guardrail_reason})
        raise HTTPException(400, guardrail_reason)

    if payload.regenerate:
        if payload.regenerate_message_id is not None:
            if not delete_assistant_message(payload.conversation_id, user_id, payload.regenerate_message_id):
                raise HTTPException(404, "Assistant message not found.")
        else:
            delete_assistant_message(payload.conversation_id, user_id)
    else:
        save_message(payload.conversation_id, user_id, "user", message)
        update_default_title(payload.conversation_id, user_id, message)

    context = build_context(payload.conversation_id, user_id, message)
    documents = retrieve_context(user_id, message)
    execution_mode = "agent" if should_use_agent(message) else "chain"
    add_trace_event(trace_id, user_id, "router_decision", payload.conversation_id,
                    details={"mode": execution_mode})
    if execution_mode == "agent":
        add_trace_event(trace_id, user_id, "agent_planned", payload.conversation_id,
                        details={"available_tools": ["calculator", "web_search"]})
    add_trace_event(trace_id, user_id, "document_retrieval", payload.conversation_id,
                    success=True, details={"chunks": len(documents)})

    async def generate() -> AsyncGenerator[str, None]:
        complete_answer = ""
        stream_status = "complete"
        try:
            add_trace_event(trace_id, user_id, "execution_started", payload.conversation_id)
            async for chunk in stream_ai_response(context, message, documents):
                if await request.is_disconnected():
                    stream_status = "cancelled"
                    break
                complete_answer += chunk
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
            if complete_answer.strip():
                save_message(payload.conversation_id, user_id, "assistant", complete_answer, stream_status)
            add_trace_event(trace_id, user_id, "response_saved", payload.conversation_id,
                            duration_ms=round((time.perf_counter() - trace_started) * 1000),
                            success=bool(complete_answer.strip()), details={"status": stream_status})
            yield json.dumps({"type": "done", "status": stream_status}) + "\n"
        except Exception:
            if complete_answer.strip():
                save_message(payload.conversation_id, user_id, "assistant", complete_answer, "failed")
            add_trace_event(trace_id, user_id, "execution_failed", payload.conversation_id,
                            duration_ms=round((time.perf_counter() - trace_started) * 1000),
                            success=False, details={"has_partial_answer": bool(complete_answer.strip())})
            yield json.dumps({
                "type": "error",
                "content": "Could not generate the AI response. Check the API key, model name, and internet connection.",
            }) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Trace-ID": trace_id},
    )
