import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from backend.database.db import get_recent_messages, search_document_chunks
from backend.agent_tools import build_agent, should_use_agent

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

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT + "\n\nUse the following private workspace context only when it is relevant:\n{document_context}"),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{message}"),
])


def build_context(conversation_id, user_id, current_message=None):
    history = get_recent_messages(conversation_id, user_id, 20)
    if (
        current_message
        and history
        and history[-1]["role"] == "user"
        and history[-1]["content"] == current_message
    ):
        history.pop()
    return history


def retrieve_context(user_id, message):
    terms = [term.lower() for term in message.split() if len(term) >= 4]
    return search_document_chunks(user_id, terms)

async def stream_ai_response(history, message, documents=None) -> AsyncGenerator[str, None]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing.")

    model = ChatGroq(
        model=MODEL_NAME,
        temperature=0.45,
        max_tokens=1800,
        api_key=api_key,
    )
    if should_use_agent(message):
        agent = build_agent(model, SYSTEM_PROMPT)
        messages = [{"role": "user", "content": item["content"]} for item in history]
        messages.append({"role": "user", "content": message})
        result = await agent.ainvoke({"messages": messages})
        final_message = result["messages"][-1]
        content = final_message.content if isinstance(final_message.content, str) else str(final_message.content)
        if content:
            yield content
        return
    chain = PROMPT | model | StrOutputParser()
    formatted_history = [
        ("human" if item["role"] == "user" else "ai", item["content"])
        for item in history
    ]
    document_context = "\n\n---\n\n".join(documents or []) or "No uploaded-document context found."
    async for content in chain.astream({"history": formatted_history, "message": message, "document_context": document_context}):
        if content:
            yield content
