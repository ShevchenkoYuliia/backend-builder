import asyncio
import json
from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from database import chat_history_collection, users_collection
from dependencies import get_current_user
from schemas import (
    AssistantDraftRequest,
    AssistantDraftResponse,
    ChatHistoryDetail,
    ChatHistoryItem,
    ChatListResponse,
    UserPublic,
)
from security import decrypt_secret
from services.assistant_service import build_draft_response, build_project_from_prompt


router = APIRouter()


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid chat history id.") from exc


def _serialize_chat_item(doc: dict) -> ChatHistoryItem:
    return ChatHistoryItem(
        id=str(doc["_id"]),
        prompt=doc["prompt"],
        assistant_message=doc["assistant_message"],
        provider=doc["provider"],
        model=doc["model"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        status=doc.get("status"),
        failed_attempts=doc.get("failed_attempts", 0),
        compile_success=doc.get("compile_success"),
        generation_time=doc.get("generation_time"),
    )


def _serialize_chat_detail(doc: dict) -> ChatHistoryDetail:
    return ChatHistoryDetail(
        id=str(doc["_id"]),
        prompt=doc["prompt"],
        assistant_message=doc["assistant_message"],
        provider=doc["provider"],
        model=doc["model"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        status=doc.get("status"),
        failed_attempts=doc.get("failed_attempts", 0),
        compile_success=doc.get("compile_success"),
        generation_time=doc.get("generation_time"),
        project=doc["project"],
    )


@router.get("/history", response_model=ChatListResponse)
async def list_history(user: UserPublic = Depends(get_current_user)) -> ChatListResponse:
    items: list[ChatHistoryItem] = []
    cursor = chat_history_collection.find({"owner_id": user.id}).sort("updated_at", -1)
    async for doc in cursor:
        items.append(_serialize_chat_item(doc))
    return ChatListResponse(items=items)


@router.get("/history/{chat_id}", response_model=ChatHistoryDetail)
async def get_history_item(
    chat_id: str,
    user: UserPublic = Depends(get_current_user),
) -> ChatHistoryDetail:
    doc = await chat_history_collection.find_one(
        {"_id": _object_id(chat_id), "owner_id": user.id}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Chat history item not found.")
    return _serialize_chat_detail(doc)


@router.post("/draft")
async def generate_draft(
    payload: AssistantDraftRequest,
    user: UserPublic = Depends(get_current_user),
):
    user_doc = await users_collection.find_one({"email": user.email})
    settings = user_doc.get("ai_settings", {})
    provider = settings.get("provider", "openai")
    encrypted_api_key = settings.get("encrypted_api_key")
    if provider != "ollama" and not encrypted_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI API key configured. Add your key in settings first.",
        )
    if provider == "custom" and not settings.get("base_url"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Custom AI provider requires a base URL.",
        )
    default_models = {
        "openai": "gpt-5-mini",
        "ollama": "llama3.1",
        "gemini": "gemini-2.5-flash",
        "claude": "claude-3-5-sonnet-20241022",
        "custom": "gpt-5-mini",
    }
    known_models = {
        "openai": {"gpt-5-mini", "gpt-5.2", "gpt-4.1", "gpt-4o-mini"},
        "ollama": {"llama3.1", "mistral", "phi3:mini"},
        "gemini": {"gemini-2.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"},
        "claude": {
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        },
    }
    model = settings.get("model", default_models.get(provider, "gpt-5-mini"))
    provider_known = known_models.get(provider)
    if provider_known and model not in provider_known:
        model = default_models.get(provider, model)
    api_key = decrypt_secret(encrypted_api_key) if encrypted_api_key else ""

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def push_progress(message: str) -> None:
            await queue.put({"type": "progress", "message": message})

        async def run_generation() -> None:
            try:
                await push_progress("Починаємо аналіз проєкту.")
                assistant_message, project, tokens_used, llm_time, failed_attempts = await build_project_from_prompt(
                    prompt=payload.prompt,
                    api_key=api_key,
                    model=model,
                    provider=provider,
                    base_url=settings.get("base_url"),
                    progress_callback=push_progress,
                )

                now = datetime.now(UTC)
                existing_doc = await chat_history_collection.find_one(
                    {"owner_id": user.id, "prompt": payload.prompt},
                    {"failed_attempts": 1},
                )
                total_failed_attempts = (
                    (existing_doc or {}).get("failed_attempts", 0) + failed_attempts
                )
                doc = {
                    "owner_id": user.id,
                    "prompt": payload.prompt,
                    "assistant_message": assistant_message,
                    "provider": settings.get("provider", "openai"),
                    "model": model,
                    "project": project.model_dump(mode="json"),
                    "updated_at": now,
                    "tokens_used": tokens_used,
                    "failed_attempts": total_failed_attempts,
                    "status": "успіх",
                }
                result = await chat_history_collection.update_one(
                    {"owner_id": user.id, "prompt": payload.prompt},
                    {
                        "$set": doc,
                        "$setOnInsert": {"created_at": now},
                    },
                    upsert=True,
                )
                chat_doc = await chat_history_collection.find_one(
                    {"owner_id": user.id, "prompt": payload.prompt}
                )
                chat_id = str(chat_doc["_id"]) if chat_doc else str(result.upserted_id)
                response = build_draft_response(
                    chat_id=chat_id,
                    prompt=payload.prompt,
                    assistant_message=assistant_message,
                    project=project,
                    provider=provider,
                    model=model,
                    created_at=now,
                    tokens_used=tokens_used,
                    llm_time=llm_time,
                )
                await queue.put(
                    {
                        "type": "result",
                        "data": {
                            **response.model_dump(mode="json"),
                            "failed_attempts": total_failed_attempts,
                        },
                    }
                )
            except HTTPException as exc:
                await queue.put(
                    {
                        "type": "error",
                        "detail": exc.detail,
                        "status_code": exc.status_code,
                    }
                )
                try:
                    now = datetime.now(UTC)
                    err_doc = {
                        "owner_id": user.id,
                        "prompt": payload.prompt,
                        "assistant_message": str(exc.detail) if hasattr(exc, "detail") else str(exc),
                        "provider": settings.get("provider", "openai"),
                        "model": model,
                        "project": {"name": "Помилка генерації", "description": "", "db_type": "postgresql", "entities": []},
                        "updated_at": now,
                        "status": "помилка",
                    }
                    await chat_history_collection.update_one(
                        {"owner_id": user.id, "prompt": payload.prompt},
                        {
                            "$set": err_doc,
                            "$inc": {"failed_attempts": 1},
                            "$setOnInsert": {"created_at": now},
                        },
                        upsert=True,
                    )
                except Exception:
                    pass
            except Exception as exc:
                await queue.put(
                    {
                        "type": "error",
                        "detail": str(exc) or "Could not generate project draft.",
                        "status_code": 500,
                    }
                )
                try:
                    now = datetime.now(UTC)
                    err_doc = {
                        "owner_id": user.id,
                        "prompt": payload.prompt,
                        "assistant_message": str(exc),
                        "provider": settings.get("provider", "openai"),
                        "model": model,
                        "project": {"name": "Помилка генерації", "description": "", "db_type": "postgresql", "entities": []},
                        "updated_at": now,
                        "status": "помилка",
                    }
                    await chat_history_collection.update_one(
                        {"owner_id": user.id, "prompt": payload.prompt},
                        {
                            "$set": err_doc,
                            "$inc": {"failed_attempts": 1},
                            "$setOnInsert": {"created_at": now},
                        },
                        upsert=True,
                    )
                except Exception:
                    pass
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_generation())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
    )
