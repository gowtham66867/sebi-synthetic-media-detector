from unittest.mock import patch

from app.services import registry


def test_exact_active_match():
    matches = registry.check_entities([{"name": "Rakesh Sharma", "role_guess": "analyst"}])
    assert matches[0].verdict == "verified_active"


def test_expired_match_flagged():
    """Covers TC F-06: a name matching an Expired/Suspended registry row must not be treated as clean."""
    matches = registry.check_entities([{"name": "Sunil Kapoor Research", "role_guess": "analyst"}])
    assert matches[0].verdict == "verified_but_expired_or_suspended"


def test_unrelated_name_no_match():
    matches = registry.check_entities([{"name": "Zzqx Totally Unrelated Name", "role_guess": "advisor"}])
    assert matches[0].verdict == "no_match"


def test_unknown_role_is_not_applicable():
    matches = registry.check_entities([{"name": "Someone", "role_guess": "unknown"}])
    assert matches[0].verdict == "not_applicable"


def test_regulator_name_is_not_applicable():
    matches = registry.check_entities([{"name": "SEBI", "role_guess": "regulator"}])
    assert matches[0].verdict == "not_applicable"


def test_fuzzy_match_boundary_below_80_is_no_match():
    """Covers TC G-01: the >=80 cutoff in registry.py must behave as an exact boundary, not approximately."""
    with patch("app.services.registry.fuzz.token_sort_ratio", return_value=79):
        matches = registry.check_entities([{"name": "Whoever", "role_guess": "advisor"}])
    assert matches[0].verdict == "no_match"


def test_fuzzy_match_boundary_at_80_is_verified():
    with patch("app.services.registry.fuzz.token_sort_ratio", return_value=80):
        matches = registry.check_entities([{"name": "Whoever", "role_guess": "advisor"}])
    assert matches[0].verdict.startswith("verified")
