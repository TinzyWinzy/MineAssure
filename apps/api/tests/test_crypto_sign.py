import base64

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.crypto_sign import (
    generate_keypair,
    sign_payload,
    verify_signature,
    verify_webcrypto_signature,
)


def test_production_requires_a_separate_signing_secret():
    common = {
        "environment": "production",
        "secret_key": "session-secret-value",
        "database_url": "postgresql+psycopg://user:pass@db.example/mineassure",
    }
    with pytest.raises(ValidationError):
        Settings(**common)
    with pytest.raises(ValidationError):
        Settings(**common, signing_key_secret="session-secret-value")
    accepted = Settings(**common, signing_key_secret="independent-signing-secret")
    assert accepted.signing_key_secret == "independent-signing-secret"


def test_development_without_signing_secret_keeps_existing_keys_readable(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "signing_key_secret", None)
    pub, encrypted = generate_keypair()
    monkeypatch.setattr(settings, "signing_key_secret", "a-new-signing-secret")
    assert verify_signature(pub, "payload-123", sign_payload(encrypted, "payload-123"))


def _webcrypto_material(message: str):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    key = ec.generate_private_key(ec.SECP256R1())
    spki = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    ).decode()
    der = key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return spki, base64.b64encode(raw).decode()


def test_sign_verify_roundtrip():
    pub, enc = generate_keypair()
    sig = sign_payload(enc, "payload-123")
    assert verify_signature(pub, "payload-123", sig) is True


def test_verify_rejects_tampered_payload():
    pub, enc = generate_keypair()
    sig = sign_payload(enc, "payload-123")
    assert verify_signature(pub, "payload-999", sig) is False


def test_verify_rejects_bad_signature():
    pub, _ = generate_keypair()
    assert verify_signature(pub, "payload-123", "AAAA") is False


def test_webcrypto_raw_signature_valid():
    msg = '{"amount":"120.00","decision":"approved"}'
    spki, sig = _webcrypto_material(msg)
    assert verify_webcrypto_signature(spki, msg, sig) is True


def test_webcrypto_raw_signature_tampered():
    spki, sig = _webcrypto_material("original")
    assert verify_webcrypto_signature(spki, "tampered", sig) is False
