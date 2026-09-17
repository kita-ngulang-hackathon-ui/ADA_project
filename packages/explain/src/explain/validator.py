"""Reject narrations that add information not in the fact sheet.

TODO:
- Extract all numbers (handle "Rp 25.000", "0.41", "41%").
- Every number must match a fact sheet value (with defined rounding rules).
- No unknown pseudonyms; max length.
"""


def validate_narration(text: str, fact_sheet) -> None:
    """Raise ValueError with a reason when the narration is not allowed."""
    raise NotImplementedError
