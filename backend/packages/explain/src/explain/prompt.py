"""LLM prompt construction (requirement 9). Temperature 0 is set by the caller."""
from explain.fact_sheet import canonical_json

SYSTEM_PROMPT = (
    "You explain a retention recommendation to a non-technical fintech operations reviewer. "
    "Use ONLY the JSON fact sheet you are given. "
    "Do not add any number, percentage, amount, date, reason, prediction, or advice that is not "
    "in the fact sheet. Do not mention user identifiers. "
    "Say which incentive is the top pick and, if present, the runner-up. "
    "Mention that the data is synthetic. "
    "Write at most 4 short sentences in plain English. "
    "Numbers may be written as they appear, as percentages of a probability, or as 'Rp' amounts."
)


def build_prompt(fact_sheet) -> tuple[str, str]:
    return SYSTEM_PROMPT, "Fact sheet:\n" + canonical_json(fact_sheet)
