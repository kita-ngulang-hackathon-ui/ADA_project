"""Arm assignment tests (README "Tests to write")."""
from measurement.assignment import CONTROL, ENGINE, NAIVE, assign_arm

SECRET = b"test-secret"


def test_assignment_is_deterministic_across_calls():
    a = assign_arm("t1", "exp1", "u_1", secret=SECRET, control_pct=20, naive_pct=20)
    b = assign_arm("t1", "exp1", "u_1", secret=SECRET, control_pct=20, naive_pct=20)
    assert a == b


def test_assignment_roughly_matches_configured_percentages():
    counts = {CONTROL: 0, NAIVE: 0, ENGINE: 0}
    for i in range(5000):
        arm = assign_arm("t1", "exp1", f"u_{i}", secret=SECRET, control_pct=20, naive_pct=20)
        counts[arm] += 1
    # Within a generous tolerance of the configured 20/20/60 split.
    assert 800 < counts[CONTROL] < 1400
    assert 800 < counts[NAIVE] < 1400
    assert 2600 < counts[ENGINE] < 3400


def test_different_users_can_get_different_arms():
    arms = {assign_arm("t1", "exp1", f"u_{i}", secret=SECRET, control_pct=20, naive_pct=20) for i in range(50)}
    assert len(arms) > 1


def test_arm_never_changes_within_experiment_across_process_runs():
    # Re-derived, not stored -- so "never changes" just means the hash is stable.
    results = [assign_arm("t1", "exp1", "u_42", secret=SECRET, control_pct=20, naive_pct=20) for _ in range(10)]
    assert len(set(results)) == 1
