from app.services.lexicon import scan_phishing_text, scan_transcript


def test_detects_multiple_categories():
    text = (
        "This is a guaranteed return, act now, and it's a confidential insider tip. "
        "Send payment to join our group."
    )
    hits = scan_transcript(text)

    assert "guaranteed_returns" in hits
    assert "urgency_pressure" in hits
    assert "insider_authority_claim" in hits
    assert "payment_solicitation" in hits


def test_clean_text_has_no_hits():
    hits = scan_transcript("The weather today is pleasant and the market opened flat.")
    assert hits == {}


def test_phishing_lexicon_detects_categories():
    text = "Dear Customer, verify your account immediately, act immediately, on behalf of sebi."
    hits = scan_phishing_text(text)

    assert "credential_harvesting" in hits
    assert "urgency_pressure" in hits
    assert "authority_impersonation" in hits
    assert "generic_greeting" in hits


def test_phishing_lexicon_clean_text_has_no_hits():
    hits = scan_phishing_text("Hi team, the meeting is at 3pm tomorrow.")
    assert hits == {}
