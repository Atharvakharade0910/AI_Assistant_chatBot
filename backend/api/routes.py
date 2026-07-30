import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.database.db import (
    clear_all_conversations,
    conversation_exists,
    create_conversation,
    delete_conversation,
    delete_last_assistant_message,
    get_messages,
    list_conversations,
    rename_conversation,
    save_message,
    update_default_title,
)
from backend.models import ChatRequest, ConversationCreate, ConversationRename
from backend.services.chat_service import build_context, stream_ai_response

router = APIRouter()

@router.get("/conversations")
def conversations():
    return list_conversations()

@router.post("/conversations")
def add_conversation(payload: ConversationCreate):
    return create_conversation(payload.title)

@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: int, payload: ConversationRename):
    if not conversation_exists(conversation_id):
        raise HTTPException(404, "Conversation not found.")
    return rename_conversation(conversation_id, payload.title)

@router.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: int):
    if not conversation_exists(conversation_id):
        raise HTTPException(404, "Conversation not found.")
    delete_conversation(conversation_id)
    return {"message": "Conversation deleted."}

@router.delete("/conversations")
def remove_all_conversations():
    clear_all_conversations()
    return {"message": "All conversations deleted."}

@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int):
    if not conversation_exists(conversation_id):
        raise HTTPException(404, "Conversation not found.")
    return get_messages(conversation_id)

@router.post("/chat")
async def chat(payload: ChatRequest, request: Request):
    message = payload.message.strip()
    if not message:
        raise HTTPException(400, "Message cannot be empty.")
    if not conversation_exists(payload.conversation_id):
        raise HTTPException(404, "Conversation not found.")

    if payload.regenerate:
        delete_last_assistant_message(payload.conversation_id)
    else:
        save_message(payload.conversation_id, "user", message)
        update_default_title(payload.conversation_id, message)

    context = build_context(payload.conversation_id)

    async def generate() -> AsyncGenerator[str, None]:
        complete_answer = ""
        try:
            async for chunk in stream_ai_response(context):
                if await request.is_disconnected():
                    break
                complete_answer += chunk
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"

            if complete_answer.strip():
                save_message(payload.conversation_id, "assistant", complete_answer)
            yield json.dumps({"type": "done"}) + "\n"
        except Exception as exc:
            print(f"Streaming error: {exc}")
            yield json.dumps({
                "type": "error",
                "content": "Could not generate the AI response. Check the API key, model name, and internet connection."
            }) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache"},
    )
