import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.fernet import Fernet



TOKEN_TTL_HOURS = int(os.getenv("ACCESS_TOKEN_TTL_HOURS", "24"))
SECRET_KEY = os.getenv(
    "APP_SECRET_KEY",
    "backend-builder-platform-dev-secret-change-me",
)
PASSWORD_ITERATIONS = 480_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return "$".join(
        [
            "pbkdf2_sha256",
            str(PASSWORD_ITERATIONS),
            _b64encode(salt),
            _b64encode(password_hash),
        ]
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected_hash = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(_b64encode(candidate), expected_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, email: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(hours=TOKEN_TTL_HOURS)
    payload = {
        "sub": subject,
        "email": email,
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, str | int]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token expired.") from exc
    except jwt.InvalidSignatureError as exc:
        raise ValueError("Invalid token signature.") from exc
    except (jwt.DecodeError, ValueError) as exc:
        raise ValueError("Invalid token format.") from exc
    except Exception as exc:
        raise ValueError("Invalid token.") from exc



def _get_fernet() -> Fernet:
    key_bytes = hashlib.sha256(SECRET_KEY.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        if not decrypted:
            raise ValueError("Stored secret could not be decrypted.")
        return decrypted
    except Exception as exc:
        raise ValueError("Stored secret could not be decrypted.") from exc


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)

