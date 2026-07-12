from unittest.mock import patch

from app.services import phishing_agent

PHISHING_SAMPLE = (
    "Dear Customer,\n"
    "This is an official SEBI compliance team notice. Your account will be suspended within 24 hours "
    "unless you verify your account immediately. Click the link below to update your KYC:\n"
    "https://sebi-verify-kyc.example.com/login\n"
    "Regards, Compliance Team"
)

BENIGN_SAMPLE = "Hi team, the quarterly board meeting is rescheduled to next Tuesday at 3pm. See you there."


def test_fallback_flags_likely_phishing():
    with patch("app.services.phishing_agent.llm_client.try_generate_json", return_value=None):
        result = phishing_agent.analyze_text(PHISHING_SAMPLE)

    assert result["extraction_method"] == "rule_based_fallback"
    assert result["verdict"] == "likely_phishing"
    assert "https://sebi-verify-kyc.example.com/login" in result["urls_found"]
    assert "requests credential/KYC/OTP verification" in result["requested_actions"]


def test_fallback_treats_benign_text_as_legitimate():
    with patch("app.services.phishing_agent.llm_client.try_generate_json", return_value=None):
        result = phishing_agent.analyze_text(BENIGN_SAMPLE)

    assert result["verdict"] == "likely_legitimate"
    assert result["red_flag_phrases"] == []


def test_llm_path_used_when_available():
    canned = {
        "claimed_sender": "SEBI",
        "urls_found": ["https://example.com"],
        "requested_actions": ["verify KYC"],
        "red_flag_phrases": ["urgent"],
        "verdict": "likely_phishing",
    }
    with patch("app.services.phishing_agent.llm_client.try_generate_json", return_value=canned):
        result = phishing_agent.analyze_text(PHISHING_SAMPLE)

    assert result["extraction_method"] == "llm"
    assert result["claimed_sender"] == "SEBI"


def test_empty_text_short_circuits():
    result = phishing_agent.analyze_text("   ")
    assert result["verdict"] == "unclear"
    assert result["urls_found"] == []
