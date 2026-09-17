"""Invariant: RLS hides other tenants' rows even without a tenant filter.

TODO: implement, then remove the skip marker. This test must never be skipped in CI.
"""
import pytest


@pytest.mark.skip(reason="skeleton: not implemented yet")
def test_rls_blocks_cross_tenant_read() -> None:
    ...
