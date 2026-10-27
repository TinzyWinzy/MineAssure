from app.attestation import attestation_hash, canonical_payload


def test_attestation_deterministic():
    parts = {"a": 1, "b": "x", "c": 2.5}
    h1 = attestation_hash(parts)
    h2 = attestation_hash(parts)
    assert h1 == h2
    assert len(h1) == 64


def test_attestation_key_order_independent():
    assert attestation_hash({"a": 1, "b": 2}) == attestation_hash({"b": 2, "a": 1})


def test_attestation_changes_with_input():
    assert attestation_hash({"a": 1}) != attestation_hash({"a": 2})


def test_canonical_payload_sorted():
    assert canonical_payload({"b": 2, "a": 1}) == '{"a":1,"b":2}'
