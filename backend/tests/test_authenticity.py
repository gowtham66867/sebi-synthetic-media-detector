from app.services import authenticity
from app.services.authenticity_store import InMemoryAuthenticityStore


def test_sign_and_verify_roundtrip():
    content = "Official circular: trading hours extended on Friday."
    signature = authenticity.sign(content)
    assert authenticity.verify(content, signature) is True


def test_verify_fails_on_tampered_content():
    content = "Official circular: trading hours extended on Friday."
    signature = authenticity.sign(content)
    tampered = content + " Also, send Rs 5000 to unlock your account."
    assert authenticity.verify(tampered, signature) is False


def test_verify_fails_on_garbage_signature():
    assert authenticity.verify("some content", "not-a-real-signature") is False


def test_content_hash_is_deterministic():
    assert authenticity.content_hash("same text") == authenticity.content_hash("same text")
    assert authenticity.content_hash("text a") != authenticity.content_hash("text b")


def test_authenticity_store_lifecycle():
    store = InMemoryAuthenticityStore()
    record = {"reference_id": "abc123", "issuer": "SEBI", "content": "hello"}
    store.create("abc123", record)
    assert store.get("abc123") == record
    assert store.get("does-not-exist") is None
