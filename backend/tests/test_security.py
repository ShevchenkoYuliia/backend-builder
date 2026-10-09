import sys
import os
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    encrypt_secret,
    decrypt_secret,
    mask_secret,
)

class TestHashPassword:
    def test_hash_returns_string(self):
        result = hash_password("secret123")
        assert isinstance(result, str)

    def test_hash_format_has_four_parts(self):
        result = hash_password("secret123")
        parts = result.split("$")
        assert len(parts) == 4, "Формат: algorithm$iterations$salt$hash"

    def test_hash_algorithm_label(self):
        result = hash_password("secret123")
        assert result.startswith("pbkdf2_sha256$")

    def test_hash_is_unique_per_call(self):
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2

    def test_verify_correct_password(self):
        password = "MyStr0ng!Pass"
        stored = hash_password(password)
        assert verify_password(password, stored) is True

    def test_verify_wrong_password(self):
        stored = hash_password("correctpassword")
        assert verify_password("wrongpassword", stored) is False

    def test_verify_empty_password(self):
        stored = hash_password("correctpassword")
        assert verify_password("", stored) is False

    def test_verify_case_sensitive(self):
        stored = hash_password("Password")
        assert verify_password("password", stored) is False
        assert verify_password("PASSWORD", stored) is False

    def test_hash_min_length_password(self):
        result = hash_password("a")
        assert verify_password("a", result) is True

    def test_hash_max_length_password(self):
        password = "A" * 128
        stored = hash_password(password)
        assert verify_password(password, stored) is True

    def test_hash_unicode_password(self):
        password = "Пароль123"
        stored = hash_password(password)
        assert verify_password(password, stored) is True

    def test_verify_corrupted_hash(self):
        assert verify_password("password", "not$a$valid$hash") is False

    def test_verify_empty_hash(self):
        assert verify_password("password", "") is False

    def test_verify_partial_hash(self):
        assert verify_password("password", "pbkdf2_sha256$480000") is False


class TestAccessToken:
    def test_create_returns_three_segments(self):
        token = create_access_token("user123", "user@test.com")
        parts = token.split(".")
        assert len(parts) == 3

    def test_decode_valid_token(self):
        token = create_access_token("user123", "user@test.com")
        payload = decode_access_token(token)
        assert payload["sub"] == "user123"
        assert payload["email"] == "user@test.com"

    def test_decode_contains_expiry(self):
        token = create_access_token("user123", "user@test.com")
        payload = decode_access_token(token)
        assert "exp" in payload
        assert payload["exp"] > int(time.time())

    def test_decode_tampered_payload_fails(self):
        import base64, json
        token = create_access_token("user123", "user@test.com")
        header, payload_b64, sig = token.split(".")
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        payload["sub"] = "hacker"
        new_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip("=")
        tampered = f"{header}.{new_payload}.{sig}"
        with pytest.raises(ValueError, match="signature"):
            decode_access_token(tampered)

    def test_decode_invalid_format_raises(self):
        with pytest.raises(ValueError):
            decode_access_token("not.a.valid.token.here")

    def test_decode_empty_token_raises(self):
        with pytest.raises(ValueError):
            decode_access_token("")

    def test_decode_only_two_segments_raises(self):
        with pytest.raises(ValueError):
            decode_access_token("header.payload")

    def test_different_subjects_produce_different_tokens(self):
        t1 = create_access_token("user1", "a@test.com")
        t2 = create_access_token("user2", "b@test.com")
        assert t1 != t2

    def test_unicode_subject_and_email(self):
        token = create_access_token("юзер_001", "тест@домен.ua")
        payload = decode_access_token(token)
        assert payload["sub"] == "юзер_001"
        assert payload["email"] == "тест@домен.ua"

class TestEncryptDecrypt:
    def test_roundtrip_basic(self):
        secret = "sk-test-1234567890"
        assert decrypt_secret(encrypt_secret(secret)) == secret

    def test_encrypt_returns_string(self):
        result = encrypt_secret("my_secret")
        assert isinstance(result, str)

    def test_encrypt_same_value_different_ciphertext(self):
        c1 = encrypt_secret("same_key")
        c2 = encrypt_secret("same_key")
        assert c1 != c2

    def test_decrypt_after_double_encrypt(self):
        original = "api-key-original"
        once = encrypt_secret(original)
        twice = encrypt_secret(once)
        assert decrypt_secret(decrypt_secret(twice)) == original

    def test_roundtrip_empty_string(self):
        secret = ""
        encrypted = encrypt_secret(secret)
        with pytest.raises(ValueError):
            decrypt_secret(encrypted)

    def test_roundtrip_long_key(self):
        secret = "sk-" + "x" * 200
        assert decrypt_secret(encrypt_secret(secret)) == secret

    def test_roundtrip_unicode(self):
        secret = "ключ-тест"
        assert decrypt_secret(encrypt_secret(secret)) == secret

    def test_decrypt_too_short_raises(self):
        import base64
        short = base64.urlsafe_b64encode(b"short").decode().rstrip("=")
        with pytest.raises(ValueError):
            decrypt_secret(short)

class TestMaskSecret:
    def test_long_key_shows_prefix_and_suffix(self):
        result = mask_secret("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "..." in result

    def test_short_key_fully_masked(self):
        result = mask_secret("12345678")
        assert result == "********"

    def test_very_short_key(self):
        result = mask_secret("abc")
        assert result == "***"

    def test_empty_string(self):
        result = mask_secret("")
        assert result == ""

    def test_exactly_8_chars_masked(self):
        result = mask_secret("12345678")
        assert all(c == "*" for c in result)

    def test_9_chars_shows_partial(self):
        result = mask_secret("123456789")
        assert "..." in result
        assert result.startswith("1234")
        assert result.endswith("6789")
