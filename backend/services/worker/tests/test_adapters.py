"""Feed adapter, LLM narrator fallback, settings, and outcome feedback tests."""
from datetime import timedelta

import httpx
import pytest
from core_contracts import Arm, OutcomeEvent
from worker import feed_adapter, llm_narrator
from worker.llm_narrator import (
    SOURCE_LLM,
    SOURCE_TEMPLATE,
    narrate_or_fallback,
    narrator_from_settings,
)
from worker.outcomes import ingest_outcomes
from worker.pipeline import run_pipeline
from worker_world import NOW, WALLET_ID, fake_scorer, make_settings


def test_canned_feed_loads_fixture() -> None:
    items, source = feed_adapter.load_feed(make_settings())
    assert source == "canned" and items
    assert {i["scope_type"] for i in items} <= {"CLIENT", "REGION", "COHORT"}


def test_live_feed_timeout_falls_back_to_canned(monkeypatch) -> None:
    def timeout(*_args, **_kwargs):
        raise httpx.ConnectTimeout("venue wifi")

    monkeypatch.setattr(feed_adapter, "_last_live_snapshot", None)
    monkeypatch.setattr(feed_adapter.httpx, "get", timeout)
    settings = make_settings(external_signal_source="live",
                             external_signal_live_base_url="http://feed.invalid/items")
    items, source = feed_adapter.load_feed(settings)
    assert source == "canned" and items


def test_live_feed_failure_uses_last_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(feed_adapter, "_last_live_snapshot", [{"scope_type": "CLIENT"}])
    monkeypatch.setattr(feed_adapter.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("x")))
    settings = make_settings(external_signal_source="live",
                             external_signal_live_base_url="http://feed.invalid/items")
    assert feed_adapter.load_feed(settings)[1] == "live_snapshot"


def test_tbd_settings_are_unset() -> None:
    settings = make_settings(explain_llm_enabled=True, explain_llm_base_url="__TBD__",
                             explain_llm_model="__TBD__", frequency_cap_window_days="__TBD__")
    assert settings.frequency_cap_window_days is None
    assert narrator_from_settings(settings) is None


class _FakeNarrator:
    def __init__(self, text) -> None:
        self.text, self.calls = text, 0

    def narrate(self, system: str, user: str) -> str:
        self.calls += 1
        if isinstance(self.text, Exception):
            raise self.text
        return self.text


def _one_fact_sheet(store, settings, monkeypatch):
    """Run the pipeline with an always-failing narrator and capture a real fact sheet."""
    import worker.pipeline as pipeline_module

    captured = []
    original = pipeline_module.narrate_or_fallback

    def spy(sheet, narrator, cache):
        captured.append(sheet)
        return original(sheet, narrator, cache)

    monkeypatch.setattr(pipeline_module, "narrate_or_fallback", spy)
    run_pipeline(WALLET_ID, "run-n", store=store, settings=settings, now=NOW, churn_scorer=fake_scorer(),
                 narrator=_FakeNarrator(RuntimeError("offline")))
    assert all(r.reason_source == SOURCE_TEMPLATE for r in store.recommendations[WALLET_ID].values())
    return captured[0]


def test_llm_disabled_or_failing_uses_template(store, settings, monkeypatch) -> None:
    sheet = _one_fact_sheet(store, settings, monkeypatch)
    text, source = narrate_or_fallback(sheet, None)
    assert source == SOURCE_TEMPLATE and "synthetic" in text


def test_llm_invented_number_falls_back_valid_text_is_used(store, settings, monkeypatch) -> None:
    sheet = _one_fact_sheet(store, settings, monkeypatch)
    bad = _FakeNarrator("This user will spend 987654 more next month.")
    assert narrate_or_fallback(sheet, bad)[1] == SOURCE_TEMPLATE

    good = _FakeNarrator("The top pick is recommended for this user; the data is synthetic.")
    cache: dict = {}
    assert narrate_or_fallback(sheet, good, cache) == (good.text, SOURCE_LLM)
    narrate_or_fallback(sheet, good, cache)
    assert good.calls == 1  # cached by fact_sheet_hash


def _stub_transport(captured: dict, content: str):
    """Capture the request body and reply with an OpenAI-shaped completion."""
    def post(url, *, headers, timeout, json):
        captured["url"], captured["headers"], captured["json"] = url, headers, json
        request = httpx.Request("POST", url)
        return httpx.Response(
            200, request=request,
            json={"choices": [{"message": {"role": "assistant", "content": content}}]},
        )

    return post


def test_narrator_sends_extra_body_and_bearer_token(monkeypatch) -> None:
    """Qwen needs chat_template_kwargs alongside the standard OpenAI fields."""
    captured: dict = {}
    monkeypatch.setattr(llm_narrator.httpx, "post", _stub_transport(captured, "Narration."))
    settings = make_settings(
        explain_llm_enabled=True,
        explain_llm_base_url="http://127.0.0.1:8000/v1/",   # trailing slash is trimmed
        explain_llm_model="qwen3-8b",
        explain_llm_api_key="secret-key",
        explain_llm_extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    narrator = narrator_from_settings(settings)
    assert narrator.narrate("system", "user") == "Narration."

    assert captured["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    body = captured["json"]
    assert body["model"] == "qwen3-8b"
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_narrator_strips_reasoning_block(monkeypatch) -> None:
    """A <think> scratchpad invents numbers the validator would reject."""
    captured: dict = {}
    reply = "<think>Maybe 987654 is right?</think>\nThe data is synthetic."
    monkeypatch.setattr(llm_narrator.httpx, "post", _stub_transport(captured, reply))
    settings = make_settings(explain_llm_enabled=True, explain_llm_model="qwen3-8b",
                             explain_llm_base_url="http://127.0.0.1:8000/v1")
    assert narrator_from_settings(settings).narrate("s", "u") == "The data is synthetic."


def test_narrator_with_only_reasoning_raises_so_template_wins(monkeypatch) -> None:
    """max_tokens spent entirely on an unclosed scratchpad is not a narration."""
    captured: dict = {}
    monkeypatch.setattr(llm_narrator.httpx, "post",
                        _stub_transport(captured, "<think>still thinking about it"))
    settings = make_settings(explain_llm_enabled=True, explain_llm_model="qwen3-8b",
                             explain_llm_base_url="http://127.0.0.1:8000/v1")
    narrator = narrator_from_settings(settings)
    with pytest.raises(ValueError):
        narrator.narrate("s", "u")


def test_outcomes_become_labeled_examples_with_counter(store, settings) -> None:
    run_pipeline(WALLET_ID, "run-f", store=store, settings=settings, now=NOW, churn_scorer=fake_scorer())
    before = len(store.load_labeled_examples(WALLET_ID))
    snapshots = store.load_feature_snapshots(WALLET_ID)
    outcomes = [
        OutcomeEvent(outcome_event_id=f"out-{n}", tenant_id=WALLET_ID, run_id=run_id,
                     user_pseudonym=user, arm=Arm.ENGINE, treated=n % 2 == 0, retained=n % 3 != 0,
                     spend_idr=10_000 if n % 2 == 0 else 0, observed_at=NOW + timedelta(days=14))
        for n, (run_id, user) in enumerate(sorted(snapshots))
    ]
    store.add_outcomes(outcomes + outcomes[:2])  # duplicates must not double count

    summary = ingest_outcomes(store, WALLET_ID, settings)
    assert summary["feedback"]["new_labeled_examples"] == len(outcomes)
    assert summary["feedback"]["total_labeled_examples"] == before + len(outcomes)
    assert summary["lift"]["synthetic_data"] is True

    again = ingest_outcomes(store, WALLET_ID, settings)
    assert again["feedback"]["new_labeled_examples"] == 0
