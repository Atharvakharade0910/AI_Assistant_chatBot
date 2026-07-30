# SimpleChat AI

A polished, beginner-friendly ChatGPT-style chatbot using **FastAPI**, **Groq API**, **SQLite**, and plain **HTML/CSS/JavaScript**.

## Features

- Real-time streaming responses
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

Copy `.env.example`, rename the copy to `.env`, and add:

```env
GROQ_API_KEY=your_actual_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
```

Run:

```powershell
python -m uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## GitHub Description

> A ChatGPT-style AI chatbot built with FastAPI, Groq API, SQLite, HTML, CSS, and JavaScript. It supports real-time streaming, contextual replies, persistent chat history, search, rename, response regeneration, Markdown, code highlighting, and dark mode.

## Resume Description

> Developed a ChatGPT-style AI chatbot using FastAPI, Groq API, SQLite, HTML, CSS, and JavaScript. Implemented real-time response streaming, persistent conversation history, contextual follow-up responses, chat management, Markdown rendering, and a responsive dark/light interface.

## Security

Never upload your `.env` file or Groq API key to GitHub.
