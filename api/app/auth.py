from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from app.config import Settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return hmac.compare_digest(expected, actual)


def create_access_token(user: CurrentUser, settings: Settings) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + (settings.access_token_minutes * 60),
    }
    return _encode_jwt(payload, settings.jwt_secret)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected = _sign(signing_input, settings.jwt_secret)
    actual = _b64decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise ValueError("Invalid token signature")

    payload = json.loads(_b64decode(payload_b64))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired")
    return payload


def _encode_jwt(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature_b64 = _b64encode(_sign(signing_input, secret))
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _sign(data: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padded = value + ("=" * (-len(value) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))

