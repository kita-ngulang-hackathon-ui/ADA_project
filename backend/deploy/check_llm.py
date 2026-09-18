"""Smoke-test the configured EXPLAIN_LLM_* endpoint.

Run from the backend directory, after filling in .env:

    uv run python deploy/check_llm.py
    make check-llm

Checks, in order: the settings are complete, the endpoint answers, and the
reply contains narration rather than only a reasoning scratchpad. It does not
touch the database and does not run the pipeline.
"""
import sys

from worker.llm_narrator import narrator_from_settings, strip_reasoning
from worker.settings import WorkerSettings

SYSTEM = (
    "You rephrase supplied facts. Never add a number that is not given to you."
)
USER = "Rewrite as one short sentence: the account is active and the data is synthetic."


def main() -> int:
    settings = WorkerSettings()

    if not settings.explain_llm_enabled:
        print("EXPLAIN_LLM_ENABLED is false; the pipeline uses template narration only.")
        print("Set it to true in .env to use the LLM.")
        return 1

    narrator = narrator_from_settings(settings)
    if narrator is None:
        print("EXPLAIN_LLM_ENABLED is true but the base URL or model is unset (or __TBD__).")
        return 1

    print(f"endpoint   {narrator.endpoint('/chat/completions')}")
    print(f"model      {narrator.model}")
    print(f"api key    {'set' if narrator.api_key else 'NOT SET'}")
    print(f"timeout    {narrator.timeout_s}s")
    print(f"extra body {narrator.extra_body or '{}'}")

    thinking = narrator.extra_body.get("chat_template_kwargs", {}).get("enable_thinking")
    if thinking is not False:
        print()
        print("WARNING: chat_template_kwargs.enable_thinking is not false.")
        print("A Qwen3 model will spend its whole token budget on a <think> block.")
        print('Set EXPLAIN_LLM_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}')

    print("\nsending a test prompt ...")
    try:
        text = narrator.narrate(SYSTEM, USER)
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic, report anything
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print("\nThe pipeline would fall back to template narration.")
        return 1

    print(f"\nreply: {text}")
    if strip_reasoning(text) != text:
        print("\nWARNING: the reply still contains a reasoning block.")
        return 1

    print("\nOK: the endpoint answers and returns usable narration.")
    print("Narrations are still validated against the fact sheet; anything that")
    print("invents a number is rejected and falls back to the template.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
