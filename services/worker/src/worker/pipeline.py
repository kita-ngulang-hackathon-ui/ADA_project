"""Pipeline orchestration (see services/worker/README.md for the 10 stages).

TODO:
- run_pipeline(tenant_id, run_id): run stages in order inside tenant_session.
- Record stage status (PENDING/RUNNING/DONE/FAILED/SKIPPED) on the run row.
- Graph stage skippable per tenant profile_type (open decision for paylater).
- Final stage writes recommendations as PENDING_APPROVAL only. Never approve.
"""


STAGES = ["INGEST", "EXTERNAL", "GRAPH", "RISK", "IMPACT", "POLICY", "RANK", "ALLOCATE", "EXPLAIN", "PERSIST"]


def run_pipeline(tenant_id: str, run_id: str) -> None:
    raise NotImplementedError
