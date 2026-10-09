import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import DB_NAME
from routes import ai_settings, assistant, auth, generate, projects, validate


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(
    title="Backend Builder API",
    description="Low-code backend generator platform",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(ai_settings.router, prefix="/api/ai-settings", tags=["ai-settings"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["assistant"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(validate.router, prefix="/api/validate", tags=["validate"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "database": DB_NAME}
