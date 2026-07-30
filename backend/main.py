from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.database.db import initialize_database

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Atharva AI",
    description="Streaming AI chatbot with SQLite history.",
    version="2.0.0",
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.include_router(router, prefix="/api")


@app.on_event("startup")
def startup_event():
    initialize_database()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "index.html")