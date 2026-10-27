"""User signing-key management."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crypto_sign import generate_keypair
from app.models import UserSigningKey


def get_or_create_user_key(db: Session, user_id: str) -> UserSigningKey:
    key = (
        db.query(UserSigningKey)
        .filter_by(user_id=user_id, revoked_at=None)
        .order_by(UserSigningKey.created_at.desc())
        .first()
    )
    if key is not None:
        return key
    public_pem, encrypted = generate_keypair()
    key = UserSigningKey(
        user_id=user_id,
        algorithm="ECDSA-P256",
        public_key_pem=public_pem,
        encrypted_private_key=encrypted,
    )
    db.add(key)
    db.flush()
    return key
