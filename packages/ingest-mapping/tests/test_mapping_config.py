"""EventTypeMapping / TenantMappingConfig tests (README "Tests to write")."""
import pytest
from core_contracts.errors import MappingError
from core_contracts.events import CanonicalEventType
from ingest_mapping.mapping_config import TenantMappingConfig
from pydantic import ValidationError


def test_wallet_and_paylater_map_to_same_canonical_types():
    wallet = TenantMappingConfig.from_dict(
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
    paylater = TenantMappingConfig.from_dict(
        "t_paylater",
        [
            {
                "client_event_type": "paylater.installment.overdue",
                "canonical_event_type": "LOAN_REPAYMENT_LATE",
                "amount_field_path": "payload.amount_due",
                "counterparty_field_path": None,
                "occurred_at_field_path": "occurred_at",
            }
        ],
    )
    assert wallet.lookup("wallet.transfer.sent").canonical_event_type == CanonicalEventType.P2P_TRANSFER
    assert (
        paylater.lookup("paylater.installment.overdue").canonical_event_type
        == CanonicalEventType.LOAN_REPAYMENT_LATE
    )


def test_unknown_event_type_raises_mapping_error():
    config = TenantMappingConfig.from_dict("t1", [])
    with pytest.raises(MappingError):
        config.lookup("nonexistent.type")


def test_inactive_mapping_is_not_looked_up():
    config = TenantMappingConfig.from_dict(
        "t1",
        [
            {
                "client_event_type": "wallet.legacy.event",
                "canonical_event_type": "PAYMENT",
                "amount_field_path": "payload.amount",
                "counterparty_field_path": None,
                "occurred_at_field_path": "occurred_at",
                "active": False,
            }
        ],
    )
    with pytest.raises(MappingError):
        config.lookup("wallet.legacy.event")


def test_duplicate_client_event_type_rejected():
    with pytest.raises(ValidationError):
        TenantMappingConfig.from_dict(
            "t1",
            [
                {
                    "client_event_type": "wallet.transfer.sent",
                    "canonical_event_type": "P2P_TRANSFER",
                    "amount_field_path": "payload.amount",
                    "counterparty_field_path": None,
                    "occurred_at_field_path": "occurred_at",
                },
                {
                    "client_event_type": "wallet.transfer.sent",
                    "canonical_event_type": "TOPUP",
                    "amount_field_path": "payload.amount2",
                    "counterparty_field_path": None,
                    "occurred_at_field_path": "occurred_at",
                },
            ],
        )
