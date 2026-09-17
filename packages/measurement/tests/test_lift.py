"""compute_lift tests (README "Tests to write")."""
from measurement.lift import compute_lift


def test_small_arm_returns_none_not_zero():
    outcomes = [
        {"arm": "CONTROL", "n": 5, "retained": 3, "spend_idr": 0},
        {"arm": "NAIVE", "n": 400, "retained": 268, "spend_idr": 9_750_000},
        {"arm": "ENGINE", "n": 400, "retained": 289, "spend_idr": 4_980_000},
    ]
    result = compute_lift(outcomes, min_arm_size=30)
    assert result["arms"]["CONTROL"]["retention_rate"] is None
    assert result["lift"]["engine_vs_control"] is None


def test_lift_vs_control_and_naive_computed_when_arms_large_enough():
    outcomes = [
        {"arm": "CONTROL", "n": 400, "retained": 232, "spend_idr": 0},
        {"arm": "NAIVE", "n": 400, "retained": 268, "spend_idr": 9_750_000},
        {"arm": "ENGINE", "n": 400, "retained": 289, "spend_idr": 4_980_000},
    ]
    result = compute_lift(outcomes, min_arm_size=30)
    assert result["arms"]["CONTROL"]["retention_rate"] == 0.58
    assert result["arms"]["ENGINE"]["retention_rate"] == 0.7225
    vs_control = result["lift"]["engine_vs_control"]
    assert round(vs_control["absolute"], 4) == round(0.7225 - 0.58, 4)
    vs_naive = result["lift"]["engine_vs_naive"]
    assert round(vs_naive["absolute"], 4) == round(0.7225 - 0.67, 4)


def test_missing_arm_treated_as_empty_not_a_crash():
    outcomes = [{"arm": "ENGINE", "n": 400, "retained": 300, "spend_idr": 1_000_000}]
    result = compute_lift(outcomes, min_arm_size=30)
    assert result["arms"]["CONTROL"]["n"] == 0
    assert result["arms"]["CONTROL"]["retention_rate"] is None


def test_synthetic_data_flag_always_present():
    result = compute_lift([], min_arm_size=30)
    assert result["synthetic_data"] is True


def test_zero_spend_gives_none_incremental_value():
    outcomes = [
        {"arm": "CONTROL", "n": 400, "retained": 232, "spend_idr": 0},
        {"arm": "NAIVE", "n": 400, "retained": 268, "spend_idr": 0},
        {"arm": "ENGINE", "n": 400, "retained": 289, "spend_idr": 0},
    ]
    result = compute_lift(outcomes, min_arm_size=30)
    assert result["lift"]["incremental_value_per_idr"]["ENGINE"] is None
