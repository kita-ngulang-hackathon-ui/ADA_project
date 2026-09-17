"""ingest-mapping unit tests."""
import json
from pathlib import Path

import pytest
from core_contracts import CanonicalEventType, MappingError
from ingest_mapping import TenantMappingConfig, normalize
from ingest_mapping.pseudonymize import pseudonymize

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "mappings"
SECRET = b"test-secret"


def _config(name: str) -> TenantMappingConfig:
    return TenantMappingConfig.from_dict(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def _raw(event_type: str, payload: dict, user_ref: str = "user-123") -> dict:
    return {
        "client_event_id": "evt-1", "event_type": event_type,
        "occurred_at": "2026-09-17T10:00:00+07:00", "user_ref": user_ref, "payload": payload,
        "user_attributes": {"region_code": "ID-JK", "cohort_key": "cohort-1", "phone": "0812"},
    }


def test_two_vocabularies_map_to_same_canonical_type() -> None:
    wallet = normalize("t-wallet", _raw("wallet.payment.merchant", {"amount": "150000"}),
                       _config("wallet.json"), SECRET)
    paylater = normalize("t-paylater", _raw("paylater.checkout.completed", {"order_total": 150000.4}),
                         _config("paylater.json"), SECRET)
    assert wallet.event_type == paylater.event_type == CanonicalEventType.PAYMENT
    assert wallet.amount_idr == paylater.amount_idr == 150000


def test_counterparty_is_pseudonymized_and_raw_ref_dropped() -> None:
    event = normalize("t", _raw("wallet.transfer.sent", {"amount": 5, "recipient_ref": "friend-9"}),
                      _config("wallet.json"), SECRET)
    dumped = event.model_dump_json()
    assert "user-123" not in dumped and "friend-9" not in dumped
    assert event.counterparty_pseudonym == pseudonymize("t", "friend-9", SECRET)
    assert event.attributes == {"region_code": "ID-JK", "cohort_key": "cohort-1"}


def test_unknown_event_type_raises() -> None:
    with pytest.raises(MappingError):
        normalize("t", _raw("wallet.mystery", {}), _config("wallet.json"), SECRET)


def test_missing_required_field_raises_mapping_error() -> None:
    with pytest.raises(MappingError):
        normalize("t", _raw("wallet.transfer.sent", {"amount": 5}), _config("wallet.json"), SECRET)


def test_same_ref_in_two_tenants_gets_unrelated_pseudonyms() -> None:
    assert pseudonymize("tenant-a", "u1", SECRET) != pseudonymize("tenant-b", "u1", SECRET)
    assert pseudonymize("tenant-a", "u1", SECRET) == pseudonymize("tenant-a", "u1", SECRET)


def test_duplicate_client_event_type_rejected() -> None:
    row = {"client_event_type": "x", "canonical_event_type": "PAYMENT"}
    with pytest.raises(ValueError):
        TenantMappingConfig.from_dict({"tenant_slug": "t", "profile_type": "WALLET",
                                       "mappings": [row, row]})


def test_inactive_mapping_raises() -> None:
    config = TenantMappingConfig.from_dict({
        "tenant_slug": "t", "profile_type": "WALLET",
        "mappings": [{"client_event_type": "x", "canonical_event_type": "PAYMENT", "active": False}],
    })
    with pytest.raises(MappingError):
        config.lookup("x")
