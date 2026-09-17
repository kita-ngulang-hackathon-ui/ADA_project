"""GET /console/v1/measurement/{experiment_id} -- arms, retention, lift vs
CONTROL and NAIVE, synthetic_data flag (requirement 10, demo beat 6).

Lift computation itself is measurement.compute_lift (L1, pure); this router
only reads persisted outcome_events/experiment_assignments and hands them to
that function. It never predicts a lift number -- only reports one measured
from posted outcomes.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from measurement.lift import compute_lift
from persistence.repositories import measurement as measurement_repo
from pydantic import BaseModel

from api import errors
from api.auth import ConsoleSession, require_console_reviewer
from api.deps import db_for_tenant
from api.settings import get_settings

router = APIRouter(prefix="/console/v1", tags=["console-measurement"])


class MeasurementOut(BaseModel):
    experiment_id: str
    name: str
    synthetic_data: bool = True
    arms: dict
    lift: dict


@router.get("/measurement/{experiment_id}")
def get_measurement(
    experiment_id: str, console: ConsoleSession = Depends(require_console_reviewer)
) -> MeasurementOut:
    try:
        experiment_uuid = uuid.UUID(experiment_id)
    except ValueError as exc:
        raise errors.not_found("experiment not found") from exc

    with db_for_tenant(console.tenant_id) as session:
        experiment = measurement_repo.get_experiment(session, tenant_id=console.tenant_id, experiment_id=experiment_uuid)
        if experiment is None:
            raise errors.not_found(f"experiment {experiment_id} not found")

        assignments = measurement_repo.list_assignments(session, tenant_id=console.tenant_id, experiment_id=experiment_uuid)
        outcomes = measurement_repo.load_outcomes(session, tenant_id=console.tenant_id, experiment_id=experiment_uuid)

    arm_by_user = {a.user_pseudonym: a.arm for a in assignments}
    retained_users: set[str] = set()
    spend_by_arm: dict[str, int] = {}
    for o in outcomes:
        if o.outcome_type == "RETAINED":
            retained_users.add(o.user_pseudonym)
        if o.value_idr:
            arm = arm_by_user.get(o.user_pseudonym)
            if arm:
                spend_by_arm[arm] = spend_by_arm.get(arm, 0) + o.value_idr

    n_by_arm: dict[str, int] = {}
    retained_by_arm: dict[str, int] = {}
    for user, arm in arm_by_user.items():
        n_by_arm[arm] = n_by_arm.get(arm, 0) + 1
        if user in retained_users:
            retained_by_arm[arm] = retained_by_arm.get(arm, 0) + 1

    outcomes_payload = [
        {"arm": arm, "n": n, "retained": retained_by_arm.get(arm, 0), "spend_idr": spend_by_arm.get(arm, 0)}
        for arm, n in n_by_arm.items()
    ]

    result = compute_lift(outcomes_payload, min_arm_size=get_settings().measurement_min_arm_size)

    return MeasurementOut(
        experiment_id=str(experiment.id),
        name=experiment.name,
        arms=result.get("arms", {}),
        lift=result.get("lift", {}),
    )
