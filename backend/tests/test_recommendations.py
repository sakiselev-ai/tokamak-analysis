from __future__ import annotations

from app.services.recommendations import generate_recommendations


def test_emergency_shutdown_above_90():
    """Probability > 0.9 should produce EMERGENCY_SHUTDOWN + INCREASE_GAS_PUFF."""
    result = {"probabilities": [0.95], "warning_issued": True}
    recs = generate_recommendations(result, threshold=0.7)
    actions = [r["action"] for r in recs]
    assert "EMERGENCY_SHUTDOWN" in actions
    assert "INCREASE_GAS_PUFF" in actions
    assert all(r["priority"] == "high" for r in recs if r["action"] in ("EMERGENCY_SHUTDOWN", "INCREASE_GAS_PUFF"))


def test_medium_priority_above_threshold():
    """Probability between threshold and 0.9 produces medium-priority recs."""
    result = {"probabilities": [0.8], "warning_issued": True}
    recs = generate_recommendations(result, threshold=0.7)
    actions = [r["action"] for r in recs]
    assert "REDUCE_HEATING" in actions
    assert "ADJUST_SHAPE" in actions
    assert all(r["priority"] == "medium" for r in recs)


def test_monitor_closely_above_50():
    """Probability between 0.5 and threshold produces MONITOR_CLOSELY."""
    result = {"probabilities": [0.6], "warning_issued": False}
    recs = generate_recommendations(result, threshold=0.7)
    actions = [r["action"] for r in recs]
    assert "MONITOR_CLOSELY" in actions
    assert recs[0]["priority"] == "low"


def test_no_recommendations_below_50():
    """Probability below 0.5 should produce no recommendations."""
    result = {"probabilities": [0.3], "warning_issued": False}
    recs = generate_recommendations(result, threshold=0.7)
    assert recs == []


def test_fast_mitigation_short_warning_time():
    """Short warning time should add FAST_MITIGATION recommendation."""
    result = {"probabilities": [0.95], "warning_issued": True, "warning_time_ms": 100}
    recs = generate_recommendations(result, threshold=0.7)
    actions = [r["action"] for r in recs]
    assert "FAST_MITIGATION" in actions
    fast = [r for r in recs if r["action"] == "FAST_MITIGATION"][0]
    assert fast["priority"] == "high"
    assert fast["timeframe_ms"] == 100


def test_no_fast_mitigation_long_warning_time():
    """Warning time >= 200ms should NOT add FAST_MITIGATION."""
    result = {"probabilities": [0.95], "warning_issued": True, "warning_time_ms": 300}
    recs = generate_recommendations(result, threshold=0.7)
    actions = [r["action"] for r in recs]
    assert "FAST_MITIGATION" not in actions


def test_empty_probabilities():
    """Missing probabilities key should fall back to [0] and produce no recommendations."""
    result = {"warning_issued": False}
    recs = generate_recommendations(result, threshold=0.7)
    assert recs == []


def test_custom_threshold():
    """Custom threshold should shift the medium-priority boundary."""
    result = {"probabilities": [0.6], "warning_issued": False}
    # With threshold=0.5, 0.6 > threshold so should get medium recs
    recs = generate_recommendations(result, threshold=0.5)
    actions = [r["action"] for r in recs]
    assert "REDUCE_HEATING" in actions


def test_recommendation_structure():
    """Each recommendation should have all required fields."""
    result = {"probabilities": [0.95], "warning_issued": True, "warning_time_ms": 50}
    recs = generate_recommendations(result, threshold=0.7)
    required_keys = {"action", "priority", "parameter", "description", "suggested_action", "timeframe_ms"}
    for rec in recs:
        assert required_keys <= set(rec.keys()), f"Missing keys in {rec}"
