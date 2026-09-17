"""explain (L1) — Fact sheet, LLM prompt, narration validator, and template fallback."""
from explain.fact_sheet import build_fact_sheet, canonical_json, fact_sheet_hash
from explain.narrator_protocol import Narrator
from explain.prompt import SYSTEM_PROMPT, build_prompt
from explain.template import render_template
from explain.validator import validate_narration

__all__ = [
    "SYSTEM_PROMPT",
    "Narrator",
    "build_fact_sheet",
    "build_prompt",
    "canonical_json",
    "fact_sheet_hash",
    "render_template",
    "validate_narration",
]
