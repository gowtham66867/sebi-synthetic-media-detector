"""Layer 2 of the brief's "Dual Protection Framework": authenticity
verification for genuine communications, via a real Ed25519 digital
signature plus a QR-coded reference a recipient can check.

Key handling: production loads SIGNING_PRIVATE_KEY_PEM from Secret Manager
(same pattern as GEMINI_API_KEY). Local dev without that env var generates an
ephemeral in-memory keypair at import time — anything signed with it won't
verify across a process restart, which is fine for local iteration and
explicitly not fine for production, where the real secret must be set.
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

from app.config import SIGNING_PRIVATE_KEY_PEM

logger = logging.getLogger(__name__)


def _load_or_generate_key() -> Ed25519PrivateKey:
    if SIGNING_PRIVATE_KEY_PEM:
        return load_pem_private_key(SIGNING_PRIVATE_KEY_PEM.encode(), password=None)
    logger.warning(
        "SIGNING_PRIVATE_KEY_PEM not set — generating an ephemeral signing key for local dev. "
        "Signatures created now will NOT verify after a process restart. Production must set "
        "the real key via Secret Manager."
    )
    return Ed25519PrivateKey.generate()


_PRIVATE_KEY = _load_or_generate_key()
_PUBLIC_KEY: Ed25519PublicKey = _PRIVATE_KEY.public_key()

PUBLIC_KEY_PEM = _PUBLIC_KEY.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def sign(content: str) -> str:
    signature = _PRIVATE_KEY.sign(content_hash(content).encode())
    return base64.b64encode(signature).decode()


def verify(content: str, signature_b64: str) -> bool:
    try:
        signature = base64.b64decode(signature_b64)
        _PUBLIC_KEY.verify(signature, content_hash(content).encode())
        return True
    except Exception:
        return False
