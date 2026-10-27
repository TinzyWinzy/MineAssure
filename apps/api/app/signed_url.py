"""Signed, time-limited URLs for private object downloads.

Uses HMAC-SHA256 over (key, expiry) with the application secret. No external
dependency. Tokens are URL-safe and self-contained; the server verifies the
signature and expiry on download.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from app.config import settings


def _secret() -> bytes:
    return settings.secret_key.encode("utf-8")


def sign(key: str, expires_in: int = 300) -> str:
    expiry = int(time.time()) + int(expires_in)
    payload = f"{key}|{expiry}"
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{key}|{expiry}|{sig}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def verify(token: str) -> str:
    # Returns the object key if valid and unexpired; raises ValueError otherwise.
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise ValueError("malformed token") from exc
    parts = raw.split("|")
    if len(parts) != 3:
        raise ValueError("malformed token")
    key, expiry_str, sig = parts
    try:
        expiry = int(expiry_str)
    except ValueError as exc:
        raise ValueError("malformed expiry") from exc
    if expiry < int(time.time()):
        raise ValueError("token expired")
    payload = f"{key}|{expiry}"
    expected = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("invalid signature")
    return key
