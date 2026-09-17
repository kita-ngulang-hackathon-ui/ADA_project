"""LLM narrator: the only generative step (requirement 9).

TODO:
- class HttpNarrator implementing explain.narrator_protocol.Narrator.
- narrate_or_fallback(fact_sheet): cache by fact_sheet_hash; call LLM when enabled;
  validate with explain.validator; on any error use explain.template.
- Store reason_source = "LLM" or "TEMPLATE".
"""
