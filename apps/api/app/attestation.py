"""Approval/export attestation (hash-based, pilot tier).

Produces a deterministic SHA-256 hash over a canonical JSON payload so that a
recorded decision can be reproduced and verified later. This is tamper-evidence,
not legal non-repudiation; upgrade to asymmetric signatures per customer need.
"""

from __future__ import annotations

import hashlib
import json


def canonical_payload(parts: dict) -> str:
    return json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)


def attestation_hash(parts: dict) -> str:
    return hashlib.sha256(canonical_payload(parts).encode("utf-8")).hexdigest()
