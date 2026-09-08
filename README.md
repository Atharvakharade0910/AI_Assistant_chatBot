# SimpleChat AI

A polished, beginner-friendly ChatGPT-style chatbot using **FastAPI**, **LangChain**, **Groq API**, **SQLite**, and plain **HTML/CSS/JavaScript**.

## Features

- Real-time streaming responses through a LangChain runnable chain
- Context-aware follow-up answers
- Multiple SQLite conversation histories
- Search and rename chats
- Delete one chat or clear all history
- Copy and regenerate AI responses
- Stop generation button
- Markdown and syntax-highlighted code
- Dark/light theme
- Responsive mobile interface
- FastAPI Swagger documentation

## Project Structure

```text
simple-ai-chatbot-v2/
├── backend/
│   ├── api/routes.py
│   ├── database/db.py
│   ├── services/chat_service.py
│   ├── main.py
│   └── models.py
├── frontend/
│   ├── css/style.css
│   ├── js/app.js
│   └── index.html
├── screenshots/
├── .env.example
├── requirements.txt
├── run.bat
└── README.md
```

## Setup

```powershell
cd simple-ai-chatbot-v2
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example`, rename the copy to `.env`, and add your Groq configuration:

```env
GROQ_API_KEY=your_actual_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
SESSION_SECRET=replace-with-a-long-random-secret
COOKIE_SECURE=false
```

Run:

```powershell
python -m uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

The application now supports multi-user accounts with signed HttpOnly session
cookies and per-user conversation ownership. Set a strong `SESSION_SECRET` in
`.env`; use `COOKIE_SECURE=true` behind HTTPS. Keep it bound to `127.0.0.1` for
local-only use.
The health endpoint is available at `http://127.0.0.1:8000/api/health`.

API documentation:

```text
http://127.0.0.1:8000/docs
```

## GitHub Description

> A ChatGPT-style AI chatbot built with FastAPI, Groq API, SQLite, HTML, CSS, and JavaScript. It supports real-time streaming, contextual replies, persistent chat history, search, rename, response regeneration, Markdown, code highlighting, and dark mode.

## Resume Description

> Developed a ChatGPT-style AI chatbot using FastAPI, Groq API, SQLite, HTML, CSS, and JavaScript. Implemented real-time response streaming, persistent conversation history, contextual follow-up responses, chat management, Markdown rendering, and a responsive dark/light interface.

## Security

Never upload your `.env` file or Groq API key to GitHub. The checked-in
`.env.example` is intentionally empty.

## AI pipeline

The application uses LangChain's `ChatGroq` integration with a
`ChatPromptTemplate`, `MessagesPlaceholder` conversation history, and
`StrOutputParser`. The resulting LangChain runnable is streamed asynchronously
to the existing FastAPI NDJSON endpoint.

Uploaded TXT, Markdown, and PDF files are stored as private per-user text
chunks and selectively added to the prompt when a question matches them. The
document API is available at `/api/documents`.

The agent path exposes two restricted tools: a safe arithmetic calculator and
a DuckDuckGo Instant Answer web lookup for current/search-style questions.
Voice input and read-aloud use the browser Web Speech APIs, so no audio is
uploaded to the server.
