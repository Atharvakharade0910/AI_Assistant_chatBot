import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException, Request, Response

SESSION_COOKIE = "simplechat_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


def _secret():
    value = os.getenv("SESSION_SECRET")
    if not value:
        raise RuntimeError("SESSION_SECRET is missing.")
    return value.encode("utf-8")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def _encode(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(raw).rstrip(b"=")
    signature = hmac.new(_secret(), body, hashlib.sha256).digest()
    signature_text = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{body.decode()}.{signature_text}"


def _decode(token: str) -> dict | None:
    try:
        body_text, signature_text = token.split(".", 1)
        body = body_text.encode()
        expected = hmac.new(_secret(), body, hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature_text + "===")
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body_text + "===").decode())
        if int(payload["exp"]) < int(time.time()):
            return None
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def set_session(response: Response, user_id: int):
    token = _encode({"sub": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    )


def clear_session(response: Response):
    response.delete_cookie(SESSION_COOKIE)


def current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    payload = _decode(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Authentication required.")
    from backend.database.db import get_user

    user = get_user(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="Session is no longer valid.")
    return user
