"""Cryptographically bound research/simulation admission proof for F-110."""
from __future__ import annotations

from hashlib import sha256

from .execution_adapter import CanonicalOrderIntent


def create_f110_admission_proof(intent: CanonicalOrderIntent) -> str:
    intent.validate()
    return sha256(f"F-110|{intent.fingerprint()}".encode("utf-8")).hexdigest()


def verify_f110_admission_proof(intent: CanonicalOrderIntent, proof: str | None) -> None:
    if not proof:
        raise PermissionError("F-110 admission proof is required")
    expected = create_f110_admission_proof(intent)
    if proof != expected:
        raise PermissionError("invalid F-110 admission proof for order intent")
