"""Transaction groups for group-based recommendations (requirement 5).

TODO:
- Find connected components (union-find) over edges above a weight floor.
- Keep groups with size >= min_size; return stable, deterministic group ids.
"""


def find_circles(edges, *, min_size: int):
    raise NotImplementedError
