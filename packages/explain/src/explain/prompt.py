"""LLM prompt construction (requirement 9).

TODO:
- SYSTEM_PROMPT: narrate only; no new numbers, reasons, or advice.
- build_prompt(fact_sheet) -> (system, user_message_json).
"""

SYSTEM_PROMPT = ""  # TODO


def build_prompt(fact_sheet) -> tuple[str, str]:
    raise NotImplementedError
