"""In-context example selection for TabPFN (requirements 3, 11).

TODO:
- Assert all rows share one tenant_id.
- Stratified sample by label, capped at max_rows, seeded.
- Raise ContextTooSmall below min_rows.
"""


def select_context(labeled_rows, *, max_rows: int, min_rows: int, seed: int):
    raise NotImplementedError
