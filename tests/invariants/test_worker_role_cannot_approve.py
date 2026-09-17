"""Invariant: app_worker cannot set APPROVED or DELIVERED (requirement 8).

TODO: implement, then remove the skip marker. This test must never be skipped in CI.
"""
import pytest


@pytest.mark.skip(reason="skeleton: not implemented yet")
def test_worker_role_cannot_approve() -> None:
    ...
