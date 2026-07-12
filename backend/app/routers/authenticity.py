"""Layer 2 of the brief's Dual Protection Framework: an issuer (SEBI, a
broker, an RE) signs an official communication and gets back a QR code +
reference ID; anyone can later check that reference to confirm the
communication is genuine and unaltered, rather than only ever being told
after the fact that something was fake.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import PUBLIC_BASE_URL
from app.services import authenticity
from app.services.authenticity_store import build_authenticity_store
from app.services.qr import make_qr_data_uri

router = APIRouter(prefix="/api/authenticity")

_MAX_CONTENT_CHARS = 20_000
_store = build_authenticity_store()


class IssueRequest(BaseModel):
    issuer: str = Field(..., min_length=1, max_length=200)
    communication_type: str = Field("circular", max_length=100)
    content: str = Field(..., min_length=1, max_length=_MAX_CONTENT_CHARS)


@router.post("/issue")
async def issue(body: IssueRequest):
    reference_id = uuid.uuid4().hex[:12]
    signature = authenticity.sign(body.content)
    issued_at = datetime.now(timezone.utc).isoformat()

    record = {
        "reference_id": reference_id,
        "issuer": body.issuer,
        "communication_type": body.communication_type,
        "content": body.content,
        "content_hash": authenticity.content_hash(body.content),
        "signature": signature,
        "issued_at": issued_at,
    }
    _store.create(reference_id, record)

    verify_url = f"{PUBLIC_BASE_URL}/verify/{reference_id}"
    return {
        "reference_id": reference_id,
        "verify_url": verify_url,
        "qr_data_uri": make_qr_data_uri(verify_url),
        "issued_at": issued_at,
    }


@router.get("/verify/{reference_id}")
async def verify(reference_id: str):
    record = _store.get(reference_id)
    if not record:
        return {"verified": False, "reason": "reference_not_found", "reference_id": reference_id}

    signature_valid = authenticity.verify(record["content"], record["signature"])
    return {
        "verified": signature_valid,
        "reference_id": reference_id,
        "issuer": record["issuer"],
        "communication_type": record["communication_type"],
        "content": record["content"],
        "content_hash": record["content_hash"],
        "issued_at": record["issued_at"],
    }
