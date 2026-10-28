"""Asymmetric per-user signing (pilot upgrade path).

Uses ECDSA P-256. Private keys are stored encrypted at rest with a key derived
from the application secret (Fernet). This is server-side key custody: it
improves tamper-evidence and integrity over HMAC, but true non-repudiation
requires user-held private keys (client-side signing) or a signing service.
"""

from __future__ import annotations

import base64
import hashlib
from typing import cast

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
)

from app.config import settings


def _fernet(secret: str | None = None) -> Fernet:
    material = secret or settings.signing_key_secret or settings.secret_key
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def _decrypt(encrypted_pem: str) -> str:
    """Decrypt with the signing secret, falling back to SECRET_KEY outside production.

    The fallback keeps pre-existing development keys readable. Production refuses
    to reuse the session secret and therefore has no fallback.
    """
    attempts = [_fernet()]
    if settings.environment != "production" and settings.signing_key_secret:
        attempts.append(_fernet(settings.secret_key))
    for fernet in attempts:
        try:
            return fernet.decrypt(encrypted_pem.encode("ascii")).decode("ascii")
        except InvalidToken:
            continue
    raise ValueError(
        "signing key could not be decrypted with the configured signing secret"
    )


def generate_keypair() -> tuple[str, str]:
    """Return (public_key_pem, encrypted_private_key_pem)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    encrypted = _fernet().encrypt(private_pem.encode("ascii")).decode("ascii")
    return public_pem, encrypted


def _load_private(encrypted_pem: str):
    private_pem = _decrypt(encrypted_pem)
    return serialization.load_pem_private_key(
        private_pem.encode("ascii"), password=None
    )


def _load_public(public_pem: str):
    return serialization.load_pem_public_key(public_pem.encode("ascii"))


def sign_payload(encrypted_private_key: str, payload: str) -> str:
    private_key = cast(EllipticCurvePrivateKey, _load_private(encrypted_private_key))
    signature = private_key.sign(payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def verify_signature(public_key_pem: str, payload: str, signature_b64: str) -> bool:
    try:
        public_key = cast(EllipticCurvePublicKey, _load_public(public_key_pem))
        padded = signature_b64 + "=" * (-len(signature_b64) % 4)
        signature = base64.urlsafe_b64decode(padded.encode("ascii"))
        public_key.verify(signature, payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def verify_webcrypto_signature(spki_b64: str, payload: str, signature_b64: str) -> bool:
    # WebCrypto ECDSA signatures are raw r||s (IEEE P1363); convert to DER.
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

        public_key = cast(
            EllipticCurvePublicKey,
            serialization.load_der_public_key(base64.b64decode(spki_b64)),
        )
        padded = signature_b64 + "=" * (-len(signature_b64) % 4)
        raw = base64.b64decode(padded)
        if len(raw) != 64:
            return False
        r = int.from_bytes(raw[:32], "big")
        s = int.from_bytes(raw[32:], "big")
        der_sig = encode_dss_signature(r, s)
        public_key.verify(der_sig, payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError, OSError):
        return False
