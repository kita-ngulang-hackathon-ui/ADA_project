"""Transaction groups for group-based recommendations (requirement 5).

Connected components (union-find) over edges; groups of size >= min_size with
deterministic ids. Groups are indivisible units for the allocator.
"""
import hashlib

from core_contracts import Circle


def find_circles(edges, *, min_size: int):
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for edge in edges:
        ra, rb = find(edge.user_pseudonym), find(edge.counterparty_pseudonym)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    groups: dict[str, list[str]] = {}
    for node in list(parent):
        groups.setdefault(find(node), []).append(node)

    circles = []
    for members in groups.values():
        if len(members) < min_size:
            continue
        ordered = tuple(sorted(members))
        circle_id = "circle-" + hashlib.sha256("|".join(ordered).encode()).hexdigest()[:12]
        circles.append(Circle(circle_id=circle_id, members=ordered))
    return sorted(circles, key=lambda c: c.circle_id)
