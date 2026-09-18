"""LLM narrator: the only generative step (requirement 9).

Provider and model are an open decision (EXPLAIN_LLM_*). HttpNarrator speaks the
OpenAI-compatible chat completions shape, which most hosted and local providers
accept, including a self-hosted Qwen3 served by vLLM. Any failure, timeout, or
validator rejection falls back to the template.

EXPLAIN_LLM_EXTRA_BODY carries provider-specific request fields. For Qwen3 it
must disable thinking; see the reasoning notes on _content below.

A base URL may carry a query string (a tunnel token, for instance
.../proxy/8000/v1?token=...). It is kept on every request path built from it.
"""
import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from explain import build_prompt, fact_sheet_hash, render_template, validate_narration

log = logging.getLogger(__name__)

SOURCE_LLM = "LLM"
SOURCE_TEMPLATE = "TEMPLATE"

# Qwen3 and other reasoning models wrap their scratchpad in <think>...</think>.
# Whether it lands in `content` or in a separate `reasoning_content` depends on
# the server's reasoning parser, so strip it here rather than relying on either.
_THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
# A truncated block: the model hit max_tokens before closing the tag, so
# everything after the opening tag is scratchpad, not narration.
_THINK_UNCLOSED = re.compile(r"<think\b[^>]*>.*\Z", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Remove a reasoning scratchpad so the validator only sees the narration."""
    return _THINK_UNCLOSED.sub("", _THINK_BLOCK.sub("", text)).strip()


class HttpNarrator:
    def __init__(self, *, base_url: str, model: str, api_key: str | None, timeout_s: float,
                 temperature: float = 0, max_tokens: int = 220,
                 extra_body: dict[str, Any] | None = None) -> None:
        parts = urlsplit(base_url)
        self._query = parts.query
        self.base_url = urlunsplit(parts._replace(query="", fragment="")).rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_body = dict(extra_body or {})

    def endpoint(self, path: str) -> str:
        """Base URL + path, with the base URL's own query string preserved."""
        url = f"{self.base_url}{path}"
        return f"{url}?{self._query}" if self._query else url

    def narrate(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        # Provider-specific fields last, so a deployment can override a default.
        payload.update(self.extra_body)
        response = httpx.post(
            self.endpoint("/chat/completions"),
            headers=headers,
            timeout=self.timeout_s,
            json=payload,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        text = strip_reasoning(message.get("content") or "")
        if not text:
            # All budget went to the scratchpad, or the server returned only
            # reasoning_content. Raising here falls back to the template.
            raise ValueError("model returned no narration outside its reasoning block")
        return text


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
        extra_body=getattr(settings, "explain_llm_extra_body", None),
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
