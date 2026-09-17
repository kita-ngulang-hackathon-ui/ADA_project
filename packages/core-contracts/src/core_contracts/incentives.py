"""Incentive catalog types. Catalog contents are an OPEN DECISION (§6).

Do not hardcode the catalog here; load it from config/fixtures
(fixtures/incentives.json).
"""
from pydantic import BaseModel, ConfigDict, field_validator


class Incentive(BaseModel):
    """One row of the incentive catalog. `encourages_borrowing` is what
    policy-guard reads for the responsible-lending rule — required, never
    inferred."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    display_name: str
    cost_idr: int
    encourages_borrowing: bool
    is_group: bool = False
    applicable_profile_types: tuple[str, ...] = ()
    active: bool = True

    @field_validator("cost_idr")
    @classmethod
    def _cost_is_int(cls, v: int) -> int:
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError("cost_idr must be a non-negative int, never a float")
        return v
