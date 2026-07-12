"""Per-IP sliding-window rate limit for the /api/analyze endpoint specifically —
that's the one that triggers real compute cost (Whisper + Gemini calls), unlike
the cheap polling GETs.

This is intentionally a plain in-memory counter, not Firestore-backed like the
job store. Rate limiting a single instance's worth of traffic is still useful
even though it resets per-instance under multi-instance scaling — the failure
mode (a burst gets a bit more headroom than intended across instances) is far
less severe than the job-store one (real jobs silently disappearing), so the
added latency/complexity of a shared backing store isn't worth it here. Worth
revisiting if this ever needs to enforce a hard per-tenant quota rather than
casual abuse protection on a demo endpoint.
"""
import threading
import time

_WINDOW_SECONDS = 3600
_MAX_REQUESTS_PER_WINDOW = 20

_lock = threading.Lock()
_requests_by_ip: dict[str, list[float]] = {}


def is_allowed(client_ip: str) -> bool:
    now = time.time()
    with _lock:
        timestamps = [t for t in _requests_by_ip.get(client_ip, []) if now - t < _WINDOW_SECONDS]
        if len(timestamps) >= _MAX_REQUESTS_PER_WINDOW:
            _requests_by_ip[client_ip] = timestamps
            return False
        timestamps.append(now)
        _requests_by_ip[client_ip] = timestamps
        return True
