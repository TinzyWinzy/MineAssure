"""Client-side public-key registration and signature verification."""

from __future__ import annotations

import base64
from typing import cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import UserPublicKey

router = APIRouter(prefix="/signing", tags=["signing"])


class RegisterKeyIn(BaseModel):
    spki_b64: str


class VerifyIn(BaseModel):
    user_id: str
    payload: str
    signature_b64: str


@router.post("/keys")
def register_key(
    body: RegisterKeyIn, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    spki = base64.b64decode(body.spki_b64)
    # Validate it parses as a public key.
    from cryptography.hazmat.primitives import serialization

    try:
        serialization.load_der_public_key(spki)
    except (ValueError, TypeError):
        raise HTTPException(422, "invalid public key")
    record = UserPublicKey(user_id=user.id, spki_b64=body.spki_b64)
    db.add(record)
    db.commit()
    return {"id": record.id, "user_id": user.id}


@router.post("/verify")
def verify(body: VerifyIn, db: Session = Depends(get_db)):
    record = (
        db.query(UserPublicKey)
        .filter_by(user_id=body.user_id, revoked_at=None)
        .order_by(UserPublicKey.created_at.desc())
        .first()
    )
    if record is None:
        raise HTTPException(404, "no public key registered")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    public_key = cast(
        EllipticCurvePublicKey,
        serialization.load_der_public_key(base64.b64decode(record.spki_b64)),
    )
    padded = body.signature_b64 + "=" * (-len(body.signature_b64) % 4)
    raw = base64.b64decode(padded)
    if len(raw) != 64:
        raise HTTPException(422, "invalid signature length")
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    der_sig = encode_dss_signature(r, s)
    try:
        public_key.verify(
            der_sig, body.payload.encode("utf-8"), ec.ECDSA(hashes.SHA256())
        )
        return {"valid": True}
    except InvalidSignature:
        return {"valid": False}
