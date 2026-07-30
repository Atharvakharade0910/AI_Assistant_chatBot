import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from groq import AsyncGroq
from backend.database.db import get_recent_messages

load_dotenv()
MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

SYSTEM_PROMPT = """
You are SimpleChat, a helpful and reliable AI assistant.
Answer directly, clearly, and naturally.
Use conversation history to understand follow-up questions.
Use headings, bullets, tables, and code blocks only when helpful.
Explain technical ideas step by step for beginners.
Do not invent facts, and clearly mention uncertainty.
Avoid irrelevant details and repetition.
""".strip()

def build_context(conversation_id):
    history = get_recent_messages(conversation_id, 20)
    return [{"role": "system", "content": SYSTEM_PROMPT}, *history]

async def stream_ai_response(messages) -> AsyncGenerator[str, None]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing.")
    client = AsyncGroq(api_key=api_key)
    stream = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.45,
        max_completion_tokens=1800,
        stream=True,
    )
    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
