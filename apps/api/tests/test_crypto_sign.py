import base64

from app.crypto_sign import (
    generate_keypair,
    sign_payload,
    verify_signature,
    verify_webcrypto_signature,
)


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
