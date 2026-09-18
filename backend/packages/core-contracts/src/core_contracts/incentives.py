"""Incentive catalog types. Catalog contents are an OPEN DECISION (§6).

Do not hardcode the catalog here; it is loaded from config/fixtures.
"""
from pydantic import BaseModel, ConfigDict


class Incentive(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    display_name: str
    cost_idr: int
    encourages_borrowing: bool = False
    # Anything touching credit limits or pricing is never allowed (§4); flagged so the guard can deny it.
    changes_credit_terms: bool = False
    is_group: bool = False
    # Empty means applicable to every profile type.
    applicable_profile_types: tuple[str, ...] = ()
    active: bool = True
