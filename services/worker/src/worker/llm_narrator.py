"""LLM narrator: the only generative step (requirement 9).

Provider and model are an open decision (EXPLAIN_LLM_*). HttpNarrator speaks the
OpenAI-compatible chat completions shape, which most hosted and local providers
accept. Any failure, timeout, or validator rejection falls back to the template.
"""
import logging
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from explain import build_prompt, fact_sheet_hash, render_template, validate_narration

log = logging.getLogger(__name__)

SOURCE_LLM = "LLM"
SOURCE_TEMPLATE = "TEMPLATE"


class HttpNarrator:
    def __init__(self, *, base_url: str, model: str, api_key: str | None, timeout_s: float,
                 temperature: float = 0, max_tokens: int = 220,
                 max_retries: int = 3, retry_backoff_s: float = 2.0) -> None:
        # base_url may itself carry a query string (e.g. a tunnel access
        # token that must ride on every request) -- append the path ahead of
        # that query string rather than after it, or the query breaks.
        parts = urlsplit(base_url)
        self._url_scheme, self._url_netloc = parts.scheme, parts.netloc
        self._url_path = parts.path.rstrip("/")
        self._url_query = parts.query
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s

    def narrate(self, system: str, user: str) -> str:
        url = urlunsplit((
            self._url_scheme, self._url_netloc,
            self._url_path + "/chat/completions",
            self._url_query, "",
        ))
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            # Qwen3 reasoning models emit chain-of-thought into a separate
            # reasoning_content field and leave `content` empty until it's
            # done; this flag skips that. Other OpenAI-compatible backends
            # ignore the unrecognized field.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        for attempt in range(self.max_retries + 1):
            response = httpx.post(
                url, headers=headers, timeout=self.timeout_s, json=payload,
            )
            # Hosted free tiers rate-limit hard; a short wait recovers the call
            # instead of silently degrading the whole run to template text.
            if response.status_code == 429 and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self.retry_backoff_s * (2 ** attempt)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
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
