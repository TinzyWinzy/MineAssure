"""Development authentication and authorization.

Dev-only login is hard-disabled when ENVIRONMENT=production.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Membership, User

# bcrypt used directly
bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode(
        "utf-8"
    )


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, memberships: list[dict]) -> str:
    expire = datetime.now(UTC) + timedelta(hours=8)
    payload = {"sub": user_id, "memberships": memberships, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from e


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing credentials"
        )
    if not dev_login_enabled():
        raise HTTPException(
            status_code=503,
            detail="Identity provider not configured; pilot auth disabled",
        )
    payload = decode_token(creds.credentials)
    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found"
        )
    # Read fresh grants on every request: revocation must not wait for JWT expiry.
    user._memberships = [
        {"org_id": m.org_id, "site_id": m.site_id, "role": m.role}
        for m in db.query(Membership).filter(Membership.user_id == user.id).all()
    ]
    return user


def dev_login_enabled() -> bool:
    return settings.environment in ("development", "test")


def authorize(user, org_id: str, site_id: str | None, *roles: str):
    grants = [
        m
        for m in memberships_of(user)
        if m["org_id"] == org_id
        and (m.get("site_id") is None or m.get("site_id") == site_id)
    ]
    if roles:
        grants = [m for m in grants if m["role"] in roles]
    if not grants:
        raise HTTPException(
            status_code=403, detail="Access to this organisation/site/action is denied"
        )


def memberships_of(user: User) -> list[dict]:
    return getattr(user, "_memberships", [])


def require_role(*roles: str):
    def dep(user: User = Depends(get_current_user)):
        ms = memberships_of(user)
        if not any(m.get("role") in roles for m in ms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role"
            )
        return user

    return dep
