"""Group recommendation bundles (requirement 5).

All members of a group reward are selected together or not at all.
"""
from allocator.items import KnapsackItem


def bundle_group(group_id: str, member_candidates):
    """Combine ranked member candidates into one indivisible item (sum cost, sum value)."""
    members = sorted(member_candidates, key=lambda r: r.candidate.candidate_id)
    if not members:
        raise ValueError("a group bundle needs at least one member")
    return KnapsackItem(
        item_id=f"bundle:{group_id}",
        choice_key=f"group:{members[0].candidate.group_id}",
        cost_idr=sum(r.candidate.cost_idr for r in members),
        value=sum(r.priority for r in members),
        candidate_ids=tuple(r.candidate.candidate_id for r in members),
    )
