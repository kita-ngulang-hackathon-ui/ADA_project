"""Reject narrations that add information not in the fact sheet.

Rules:
- Every number in the text must match a fact sheet number, directly, rounded to
  1-3 decimals, or as a percentage (x100) rounded to 0-1 decimals. Signs are ignored.
  "Rp 25.000" / "25,000" read as 25000; "0.410" reads as a decimal.
- Hex identifiers (12+ chars) must appear in the fact sheet.
- Length is capped.
"""
import re

from core_contracts import NarrationRejected

MAX_CHARS = 1200

_HEX_ID = re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.,])\d[\d.,]*")
# "Rp25.000": the digits follow a word character, so split them off first.
_RP_GLUED = re.compile(r"Rp\.?(?=\d)")
_THOUSANDS = re.compile(r"^[1-9]\d{0,2}([.,]\d{3})+$")
_TOL = 1e-6


def _interpretations(token: str, *, rupiah: bool = False) -> set[float]:
    token = token.rstrip(".,")
    values: set[float] = set()
    if _THOUSANDS.match(token):
        values.add(float(re.sub(r"[.,]", "", token)))
        if rupiah:  # "Rp 50.000" is fifty thousand, never 50.0
            return values
    if token.count(".") <= 1 and "," not in token:
        values.add(float(token))
    elif token.count(",") == 1 and "." not in token:
        values.add(float(token.replace(",", ".")))
    return values


def extract_numbers(text: str) -> list[set[float]]:
    text = _RP_GLUED.sub("Rp ", _HEX_ID.sub(" ", text))
    found = []
    for match in _NUMBER.finditer(text):
        rupiah = re.search(r"Rp\.?\s*$", text[max(0, match.start() - 4):match.start()]) is not None
        options = _interpretations(match.group(), rupiah=rupiah)
        if options:
            found.append(options)
    return found


def _walk(node, numbers: set[float], strings: list[str]) -> None:
    if isinstance(node, bool) or node is None:
        return
    if isinstance(node, (int, float)):
        numbers.add(abs(float(node)))
    elif isinstance(node, str):
        strings.append(node)
        for options in extract_numbers(node):
            numbers.update(options)
    elif isinstance(node, dict):
        for value in node.values():
            _walk(value, numbers, strings)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _walk(value, numbers, strings)


def allowed_numbers(fact_sheet) -> set[float]:
    raw: set[float] = set()
    strings: list[str] = []
    _walk(fact_sheet.model_dump(mode="json"), raw, strings)
    allowed = set(raw)
    for v in raw:
        for d in (1, 2, 3):
            allowed.add(round(v, d))
        for d in (0, 1):
            allowed.add(round(v * 100, d))
    return allowed


def validate_narration(text: str, fact_sheet) -> None:
    """Raise NarrationRejected (a ValueError) with a reason when the narration is not allowed."""
    if not text or not text.strip():
        raise NarrationRejected("narration is empty")
    if len(text) > MAX_CHARS:
        raise NarrationRejected(f"narration longer than {MAX_CHARS} characters")

    numbers: set[float] = set()
    strings: list[str] = []
    _walk(fact_sheet.model_dump(mode="json"), numbers, strings)
    known_text = " ".join(strings).lower()
    for ident in _HEX_ID.findall(text):
        if ident.lower() not in known_text:
            raise NarrationRejected(f"unknown identifier {ident[:6]}...")

    allowed = allowed_numbers(fact_sheet)
    for options in extract_numbers(text):
        if not any(abs(o - a) <= _TOL for o in options for a in allowed):
            shown = min(options)
            raise NarrationRejected(f"number {shown:g} is not in the fact sheet")
