"""Structural tests for persistence.models that need no live database.

Full integration coverage (idempotent insert, RLS, role grants) requires
Postgres -- see tests/invariants/, which the README already documents as
needing `docker compose up postgres`.
"""
from persistence.models import RLS_TABLE_NAMES, Base

EXPECTED_TABLES = {
    "tenants", "api_keys", "event_type_mappings", "incentives",
    "raw_events", "canonical_events", "external_signals",
    "users", "counterparty_nodes", "relationship_edges",
    "transaction_circles", "circle_members",
    "risk_scores", "impact_scores",
    "pipeline_runs", "policy_decisions",
    "allocation_runs", "allocation_candidates",
    "recommendations", "narrations", "contact_log",
    "experiments", "experiment_assignments", "outcome_events",
    "labeled_examples", "audit_log", "feature_snapshots",
}


def test_all_expected_tables_are_defined():
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_every_domain_table_has_tenant_id_except_the_tenant_row_itself():
    for name, table in Base.metadata.tables.items():
        if name == "tenants":
            continue
        assert "tenant_id" in table.columns, f"{name} is missing tenant_id"


def test_external_signals_has_no_user_column():
    """Invariant: external_signals carries no user or counterparty column
    (tests/invariants/test_external_signals_have_no_user_column.py mirrors
    this against a live database; this is the fast, DB-free version)."""
    table = Base.metadata.tables["external_signals"]
    column_names = set(table.columns.keys())
    assert not any("user" in c or "counterparty" in c for c in column_names)


def test_counterparty_nodes_has_no_attribute_columns():
    table = Base.metadata.tables["counterparty_nodes"]
    column_names = set(table.columns.keys())
    allowed = {"tenant_id", "counterparty_pseudonym", "last_seen_at", "event_count_30d", "is_active", "is_own_user"}
    assert column_names == allowed


def test_rls_table_names_excludes_tenants_and_api_keys():
    assert "tenants" not in RLS_TABLE_NAMES
    assert "api_keys" not in RLS_TABLE_NAMES
    assert "recommendations" in RLS_TABLE_NAMES
    assert len(RLS_TABLE_NAMES) == len(EXPECTED_TABLES) - 2


def test_recommendations_check_constraints_present():
    table = Base.metadata.tables["recommendations"]
    check_names = {c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"}
    assert "ck_recommendations_approved_needs_reviewer" in check_names
    assert "ck_recommendations_delivered_needs_review_and_delivery" in check_names
    assert "ck_recommendations_subject_exclusive" in check_names


def test_raw_events_idempotency_constraint_present():
    table = Base.metadata.tables["raw_events"]
    unique_names = {c.name for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"}
    assert "uq_raw_events_idempotency" in unique_names
