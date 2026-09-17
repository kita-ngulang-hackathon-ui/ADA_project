"""Worker settings from environment / .env.

Values left as "__TBD__" (open decisions, REQUIREMENTS §6) become None. The
frequency cap in particular is never defaulted: None makes the policy guard
fail closed.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TBD = "__TBD__"


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Secrets
    pseudonym_hmac_secret: str
    measurement_hmac_secret: str

    # Worker
    worker_batch_size: int = 500

    # External signals (requirement 2)
    external_signal_source: str = "canned"  # canned | live (open decision)
    external_signal_fixture_dir: str = "fixtures/external"
    external_signal_live_base_url: str | None = None
    external_signal_live_timeout_s: float = 3.0
    external_signal_max_age_days: int = 14

    # Graph (requirement 4)
    pipeline_graph_lookback_days: int = 90
    pipeline_activity_window_days: int = 30
    pipeline_min_edge_interactions: int = 3
    pipeline_circle_min_size: int = 3
    pipeline_edge_decay_halflife_days: float = 21
    pattern_dip_threshold: float = 0.10
    pattern_cohort_dip_threshold: float = 0.30
    # Profile types that get the relationship-graph stage. Paylater/LENDING is an open decision (§6).
    pipeline_graph_profiles: str = "WALLET"
    # Business value of keeping a user = monthly IDR volume x this many months.
    pipeline_business_value_months: int = 3

    # TabPFN / risk (requirement 3)
    tabpfn_enabled: bool = True
    tabpfn_model_cache_dir: str | None = None
    tabpfn_seed: int = 42
    tabpfn_max_context_rows: int = 1000
    risk_min_context_rows: int = 30

    # Intervention Impact Engine (requirement 6)
    impact_seed: int = 42
    impact_min_train_rows: int = 200
    impact_threshold: float = 0.05
    impact_sure_thing_p_not_incentivized: float = 0.80

    # Decision Engine (requirement 7)
    ranker_min_context_rows: int = 100
    allocator_strategy: str = "auto"
    allocator_cost_scale_idr: int = 1000
    allocator_max_dp_cells: int = 20_000_000
    default_budget_idr: int = 5_000_000

    # Policy guard
    frequency_cap_max_contacts: int | None = None
    frequency_cap_window_days: int | None = None
    responsible_lending_lookback_days: int = 60
    responsible_lending_min_late_events: int = 1

    # Explanation / LLM (requirement 9)
    explain_llm_enabled: bool = False
    explain_llm_base_url: str | None = None
    explain_llm_model: str | None = None
    explain_llm_api_key: str | None = None
    explain_llm_timeout_s: float = 6
    explain_llm_temperature: float = 0
    explain_llm_max_tokens: int = 220

    # Measurement (requirement 10)
    measurement_control_pct: int = 20
    measurement_naive_pct: int = 20
    measurement_naive_risk_threshold: float = 0.60
    measurement_min_arm_size: int = 30

    # Continual improvement (requirement 11)
    feedback_use_in_context: bool = True
    feedback_min_rows_per_cycle: int = 10

    @field_validator(
        "frequency_cap_max_contacts", "frequency_cap_window_days", "external_signal_live_base_url",
        "explain_llm_base_url", "explain_llm_model", "explain_llm_api_key",
        "tabpfn_model_cache_dir", mode="before",
    )
    @classmethod
    def _tbd_is_unset(cls, value):
        if isinstance(value, str) and value.strip() in ("", TBD):
            return None
        return value

    @property
    def graph_profiles(self) -> frozenset[str]:
        return frozenset(p.strip().upper() for p in self.pipeline_graph_profiles.split(",") if p.strip())
