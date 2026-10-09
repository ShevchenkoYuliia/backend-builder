from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from database import users_collection
from dependencies import get_current_user
from schemas import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from security import create_access_token, hash_password, verify_password


router = APIRouter()


def _serialize_user(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        email=doc["email"],
        full_name=doc["full_name"],
        created_at=doc["created_at"],
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest) -> AuthResponse:
    existing = await users_collection.find_one({"email": payload.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    now = datetime.now(UTC)
    doc = {
        "email": payload.email,
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
        "created_at": now,
    }
    result = await users_collection.insert_one(doc)
    created = await users_collection.find_one({"_id": result.inserted_id})
    token = create_access_token(str(result.inserted_id), payload.email)
    return AuthResponse(access_token=token, user=_serialize_user(created))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    user = await users_collection.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(str(user["_id"]), user["email"])
    return AuthResponse(access_token=token, user=_serialize_user(user))


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return user
