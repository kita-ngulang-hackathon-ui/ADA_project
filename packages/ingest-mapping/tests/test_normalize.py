"""normalize() and pseudonymize() tests (README "Tests to write")."""
import pytest
from core_contracts.errors import MappingError
from ingest_mapping.mapping_config import TenantMappingConfig
from ingest_mapping.normalize import normalize
from ingest_mapping.pseudonymize import pseudonymize

SECRET = b"test-secret"

WALLET_CONFIG = TenantMappingConfig.from_dict(
    "t_wallet",
    [
        {
            "client_event_type": "wallet.transfer.sent",
            "canonical_event_type": "P2P_TRANSFER",
            "amount_field_path": "payload.amount",
            "counterparty_field_path": "payload.recipient_id",
            "occurred_at_field_path": "occurred_at",
        }
    ],
)

RAW_EVENT = {
    "client_event_id": "evt_1",
    "event_type": "wallet.transfer.sent",
    "occurred_at": "2026-09-17T10:04:31+07:00",
    "user_ref": "usr_8831",
    "user_attributes": {"region_code": "ID-JK", "cohort_key": "students-2025", "device_id": "should-be-dropped"},
    "payload": {"amount": 150000, "recipient_id": "usr_2204", "channel": "qris"},
}


def test_normalize_produces_canonical_event():
    event = normalize("t_wallet", RAW_EVENT, WALLET_CONFIG, SECRET)
    assert event.amount_idr == 150000
    assert event.event_type.value == "P2P_TRANSFER"
    assert event.user_pseudonym != "usr_8831"
    assert event.counterparty_pseudonym is not None


def test_output_never_contains_raw_user_ref():
    event = normalize("t_wallet", RAW_EVENT, WALLET_CONFIG, SECRET)
    dumped = event.model_dump_json()
    assert "usr_8831" not in dumped
    assert "usr_2204" not in dumped


def test_non_whitelisted_attribute_dropped():
    event = normalize("t_wallet", RAW_EVENT, WALLET_CONFIG, SECRET)
    assert "device_id" not in event.attributes
    assert event.attributes["region_code"] == "ID-JK"


def test_unknown_event_type_raises_mapping_error():
    raw = {**RAW_EVENT, "event_type": "wallet.unknown.thing"}
    with pytest.raises(MappingError):
        normalize("t_wallet", raw, WALLET_CONFIG, SECRET)


def test_same_raw_ref_different_tenants_gives_different_pseudonyms():
    a = pseudonymize("tenant_a", "usr_8831", SECRET)
    b = pseudonymize("tenant_b", "usr_8831", SECRET)
    assert a != b


def test_pseudonymize_is_deterministic():
    a = pseudonymize("tenant_a", "usr_8831", SECRET)
    b = pseudonymize("tenant_a", "usr_8831", SECRET)
    assert a == b
