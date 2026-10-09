from bson import ObjectId
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from database import users_collection
from dependencies import get_current_user
from schemas import (
    AIKeyDeleteResponse,
    AISettingsPublic,
    AISettingsUpdateRequest,
    UserPublic,
)
from security import encrypt_secret, mask_secret


router = APIRouter()


def _settings_public(user_doc: dict) -> AISettingsPublic:
    settings = user_doc.get("ai_settings", {})
    encrypted_key = settings.get("encrypted_api_key")
    masked = settings.get("api_key_masked")
    return AISettingsPublic(
        provider=settings.get("provider", "openai"),
        model=settings.get("model", "gpt-5-mini"),
        base_url=settings.get("base_url"),
        api_key_present=bool(encrypted_key),
        api_key_masked=masked,
        updated_at=settings.get("updated_at"),
    )


@router.get("/", response_model=AISettingsPublic)
async def get_settings(user: UserPublic = Depends(get_current_user)) -> AISettingsPublic:
    user_doc = await users_collection.find_one({"_id": ObjectId(user.id)})
    return _settings_public(user_doc)


@router.put("/", response_model=AISettingsPublic)
async def update_settings(
    payload: AISettingsUpdateRequest,
    user: UserPublic = Depends(get_current_user),
) -> AISettingsPublic:
    update_doc = {
        "ai_settings.provider": payload.provider.value,
        "ai_settings.model": payload.model,
        "ai_settings.updated_at": datetime.now(UTC),
    }
    if payload.provider.value == "custom":
        update_doc["ai_settings.base_url"] = (payload.base_url or "").rstrip("/")
    else:
        update_doc["ai_settings.base_url"] = None

    if payload.api_key:
        update_doc["ai_settings.encrypted_api_key"] = encrypt_secret(payload.api_key)
        update_doc["ai_settings.api_key_masked"] = mask_secret(payload.api_key)

    await users_collection.update_one({"_id": ObjectId(user.id)}, {"$set": update_doc})
    user_doc = await users_collection.find_one({"_id": ObjectId(user.id)})
    return _settings_public(user_doc)


@router.delete("/key", response_model=AIKeyDeleteResponse)
async def delete_api_key(
    user: UserPublic = Depends(get_current_user),
) -> AIKeyDeleteResponse:
    await users_collection.update_one(
        {"_id": ObjectId(user.id)},
        {
            "$set": {
                "ai_settings.updated_at": datetime.now(UTC),
            },
            "$unset": {
                "ai_settings.encrypted_api_key": "",
                "ai_settings.api_key_masked": "",
            },
        },
    )
    return AIKeyDeleteResponse(message="API key removed.")
