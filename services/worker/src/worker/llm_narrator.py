"""LLM narrator: the only generative step (requirement 9).

Provider and model are an open decision (EXPLAIN_LLM_*). HttpNarrator speaks the
OpenAI-compatible chat completions shape, which most hosted and local providers
accept. Any failure, timeout, or validator rejection falls back to the template.
"""
import logging

import httpx
from explain import build_prompt, fact_sheet_hash, render_template, validate_narration

log = logging.getLogger(__name__)

SOURCE_LLM = "LLM"
SOURCE_TEMPLATE = "TEMPLATE"


class HttpNarrator:
    def __init__(self, *, base_url: str, model: str, api_key: str | None, timeout_s: float,
                 temperature: float = 0, max_tokens: int = 220) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.max_tokens = max_tokens

    def narrate(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            timeout=self.timeout_s,
            json={
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


def narrator_from_settings(settings) -> HttpNarrator | None:
    """None (template only) unless the LLM is enabled and its open-decision settings are filled."""
    if not settings.explain_llm_enabled:
        return None
    if not settings.explain_llm_base_url or not settings.explain_llm_model:
        log.warning("EXPLAIN_LLM_ENABLED but base URL/model are unset; using template narration")
        return None
    return HttpNarrator(
        base_url=settings.explain_llm_base_url, model=settings.explain_llm_model,
        api_key=settings.explain_llm_api_key, timeout_s=settings.explain_llm_timeout_s,
        temperature=settings.explain_llm_temperature, max_tokens=settings.explain_llm_max_tokens,
    )


def narrate_or_fallback(fact_sheet, narrator, cache: dict | None = None) -> tuple[str, str]:
    """Return (reason_text, reason_source). Cached by fact_sheet_hash."""
    key = fact_sheet_hash(fact_sheet)
    if cache is not None and key in cache:
        return cache[key]
    result = (render_template(fact_sheet), SOURCE_TEMPLATE)
    if narrator is not None:
        try:
            system, user = build_prompt(fact_sheet)
            text = narrator.narrate(system, user)
            validate_narration(text, fact_sheet)
            result = (text, SOURCE_LLM)
        except Exception as exc:
            log.info("narration fell back to template (%s)", type(exc).__name__)
    if cache is not None:
        cache[key] = result
    return result
