from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import users_collection
from schemas import UserPublic
from security import decode_access_token


auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> UserPublic:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload["sub"]
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from exc

    try:
        object_id = ObjectId(str(user_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user reference in token.",
        ) from exc

    user = await users_collection.find_one({"_id": object_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    return UserPublic(
        id=str(user["_id"]),
        email=user["email"],
        full_name=user["full_name"],
        created_at=user["created_at"],
    )
