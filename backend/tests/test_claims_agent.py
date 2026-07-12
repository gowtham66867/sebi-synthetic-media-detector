from unittest.mock import patch

from app.services import claims_agent

SCRIPT = (
    "Hello everyone, this is a confidential SEBI Insider tip. "
    "I am Rakesh Gupta from SEBI Approved Advisory. "
    "I have guaranteed returns for you today. "
    "Act now, this offer is only for today. "
    "Send payment to join our exclusive Telegram group for guaranteed calls."
)


def test_fallback_used_when_llm_unavailable():
    """Covers TC R-01: LLM failure must degrade to the rule-based extractor, not raise."""
    with patch("app.services.claims_agent.llm_client.try_generate_json", return_value=None):
        result = claims_agent.extract_claims(SCRIPT)

    assert result["extraction_method"] == "rule_based_fallback"
    names = {e["name"] for e in result["claimed_entities"]}
    assert "Rakesh Gupta" in names  # regression test for the IGNORECASE-over-capture bug
    assert "SEBI" in names
    assert result["overall_intent"] == "stock_promotion"
    assert any("guaranteed return" in p.lower() for p in result["red_flag_phrases"])


def test_llm_path_used_when_available():
    canned = {
        "claimed_entities": [{"name": "Test Advisor", "role_guess": "advisor"}],
        "financial_claims": ["buy this stock"],
        "red_flag_phrases": ["guaranteed return"],
        "overall_intent": "stock_promotion",
    }
    with patch("app.services.claims_agent.llm_client.try_generate_json", return_value=canned):
        result = claims_agent.extract_claims(SCRIPT)

    assert result["extraction_method"] == "llm"
    assert result["claimed_entities"] == canned["claimed_entities"]


def test_empty_transcript_short_circuits():
    result = claims_agent.extract_claims("   ")
    assert result == {
        "claimed_entities": [],
        "financial_claims": [],
        "red_flag_phrases": [],
        "overall_intent": "unclear",
        "extraction_method": "llm",
    }
