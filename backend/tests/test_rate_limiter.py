from app.services import rate_limiter


def test_allows_up_to_the_limit_then_blocks(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_MAX_REQUESTS_PER_WINDOW", 3)
    monkeypatch.setattr(rate_limiter, "_requests_by_ip", {})

    ip = "10.0.0.1"
    assert rate_limiter.is_allowed(ip) is True
    assert rate_limiter.is_allowed(ip) is True
    assert rate_limiter.is_allowed(ip) is True
    assert rate_limiter.is_allowed(ip) is False  # 4th request in the window is blocked


def test_different_ips_have_independent_limits(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_MAX_REQUESTS_PER_WINDOW", 1)
    monkeypatch.setattr(rate_limiter, "_requests_by_ip", {})

    assert rate_limiter.is_allowed("10.0.0.1") is True
    assert rate_limiter.is_allowed("10.0.0.1") is False
    assert rate_limiter.is_allowed("10.0.0.2") is True  # unaffected by the other IP's limit


def test_old_requests_outside_the_window_are_forgotten(monkeypatch):
    monkeypatch.setattr(rate_limiter, "_MAX_REQUESTS_PER_WINDOW", 1)
    monkeypatch.setattr(rate_limiter, "_requests_by_ip", {"10.0.0.1": [0.0]})  # far in the past

    assert rate_limiter.is_allowed("10.0.0.1") is True
