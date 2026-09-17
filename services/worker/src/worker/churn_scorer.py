"""Resident trained TabPFN churn scorer (see TABPFN_CHURN_SCORER_INTEGRATION.md).

Loads the versioned artifact bundle once per process:
  synthetic_churn_context.parquet, context_schema.json, run_metadata.json.
Fit supplies the saved labeled context only (rows with split == "context");
there is no gradient fine-tuning. Rows marked "holdout" never reach the model.

`python -m worker.churn_scorer --verify` checks hashes and schema without fitting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA_VERSION = "1.0.0"
PARQUET_NAME = "synthetic_churn_context.parquet"
SCHEMA_NAME = "context_schema.json"
METADATA_NAME = "run_metadata.json"


class ChurnScorerUnavailable(RuntimeError):
    """The trained scorer is enabled but cannot be loaded or was not provided."""


def _default_classifier_factory(**kwargs):
    from tabpfn import TabPFNClassifier

    return TabPFNClassifier(**kwargs)


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ArtifactBundle:
    """The three artifact files, checked for presence, schema version, and integrity."""

    def __init__(self, artifact_dir: str | Path, *, verify_hashes: bool = True) -> None:
        self.artifact_dir = Path(artifact_dir)
        self.parquet_path = self.artifact_dir / PARQUET_NAME
        self.schema_path = self.artifact_dir / SCHEMA_NAME
        self.metadata_path = self.artifact_dir / METADATA_NAME

        for path in (self.parquet_path, self.schema_path, self.metadata_path):
            if not path.is_file():
                raise FileNotFoundError(f"Missing scorer artifact: {path}")

        self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))

        if self.schema.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema version: {self.schema.get('schema_version')!r}")

        if verify_hashes:
            self._verify_hashes()

    def _verify_hashes(self) -> None:
        recorded = self.metadata.get("artifacts", {})
        for path in (self.parquet_path, self.schema_path):
            expected = recorded.get(path.name, {}).get("sha256")
            if not expected:
                raise ValueError(f"No recorded SHA-256 hash for {path.name}")
            actual = _sha256(path)
            if actual != expected:
                raise ValueError(
                    f"Artifact integrity check failed for {path.name}: "
                    f"expected {expected}, received {actual}"
                )

    @property
    def parquet_sha256(self) -> str:
        recorded = self.metadata.get("artifacts", {}).get(PARQUET_NAME, {}).get("sha256")
        return recorded or _sha256(self.parquet_path)


class ChurnRiskScorer:
    """Load a saved TabPFN context once and score user snapshots."""

    def __init__(
        self,
        artifact_dir: str | Path,
        *,
        device: str = "auto",
        verify_hashes: bool = True,
        allow_cpu_large_context: bool = True,
        classifier_factory: Callable = _default_classifier_factory,
    ) -> None:
        self.bundle = ArtifactBundle(artifact_dir, verify_hashes=verify_hashes)
        self.schema = self.bundle.schema
        self.metadata = self.bundle.metadata
        self.device = resolve_device(device)

        feature_specs = self.schema["model_features_ordered"]
        self.feature_names = [item["name"] for item in feature_specs]
        self.target_name = self.schema["target"]["name"]
        self.positive_class = self.schema["target"]["positive_class"]
        self.categorical_categories = {
            item["name"]: item["categories"] for item in feature_specs if item["kind"] == "categorical"
        }
        self.numeric_features = [item["name"] for item in feature_specs if item["kind"] == "numerical"]

        table = pd.read_parquet(self.bundle.parquet_path)
        self._restore_categories(table)

        split = self.schema["split"]
        context = table[table[split["column"]].astype(str) == split["context_value"]].copy()
        if context.empty:
            raise ValueError("The artifact contains no TabPFN context rows")

        X_context = context[self.feature_names].copy()
        y_context = context[self.target_name].astype("int64").copy()
        if set(y_context.unique()) != {0, 1}:
            raise ValueError("The saved context must contain both binary target classes")
        self.context_row_count = len(X_context)

        constructor = self.metadata["tabpfn"]["constructor"].copy()
        constructor["device"] = self.device
        constructor["categorical_features_indices"] = [
            self.feature_names.index(name) for name in self.categorical_categories
        ]

        # TabPFN refuses >5000 context rows on CPU unless allowed; the bundle has ~9k (slower, same model).
        if self.device == "cpu" and allow_cpu_large_context:
            os.environ.setdefault("TABPFN_ALLOW_CPU_LARGE_DATASET", "1")

        # TabPFN fit supplies labeled context; it does not fine-tune model weights.
        self.model = classifier_factory(**constructor)
        self.model.fit(X_context, y_context)

        matching = np.flatnonzero(np.asarray(self.model.classes_) == self.positive_class)
        if len(matching) != 1:
            raise ValueError(f"Positive class {self.positive_class!r} is absent from model classes")
        self.positive_class_position = int(matching[0])

    @property
    def model_name(self) -> str:
        return f"TABPFN_ARTIFACT_{self.bundle.parquet_sha256[:8]}"

    def _restore_categories(self, frame: pd.DataFrame) -> None:
        for column, categories in self.categorical_categories.items():
            frame[column] = pd.Categorical(frame[column], categories=categories)

    def _prepare_candidates(self, candidates: pd.DataFrame) -> pd.DataFrame:
        required = {"user_id", "snapshot_date", *self.feature_names}
        missing = sorted(required.difference(candidates.columns))
        if missing:
            raise ValueError(f"Candidate data is missing columns: {missing}")
        if candidates["user_id"].isna().any():
            raise ValueError("Candidate user_id cannot be missing")
        if pd.to_datetime(candidates["snapshot_date"], errors="coerce").isna().any():
            raise ValueError("Candidate snapshot_date contains invalid dates")

        X = candidates[self.feature_names].copy()
        for column in self.numeric_features:
            X[column] = pd.to_numeric(X[column], errors="coerce")
            if X[column].isna().any():
                raise ValueError(f"Candidate feature {column} contains invalid values")
        for column, categories in self.categorical_categories.items():
            supplied = set(X[column].dropna().astype(str).unique())
            unknown = sorted(supplied.difference(categories))
            if unknown:
                raise ValueError(f"Candidate feature {column} contains unknown categories: {unknown}")
            X[column] = pd.Categorical(X[column], categories=categories)
            if X[column].isna().any():
                raise ValueError(f"Candidate feature {column} contains missing values")
        return X

    def _positive(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.model.predict_proba(X))[:, self.positive_class_position].astype(float)

    def predict(self, candidates: pd.DataFrame) -> pd.DataFrame:
        """Return user_id, churn_risk, and as_of for a candidate batch."""
        X = self._prepare_candidates(candidates)
        return pd.DataFrame(
            {
                "user_id": candidates["user_id"].astype(str).to_numpy(),
                "churn_risk": self._positive(X),
                "as_of": pd.to_datetime(candidates["snapshot_date"]).dt.date.astype(str).to_numpy(),
            },
            index=candidates.index,
        )

    def predict_with_neutral(self, candidates: pd.DataFrame, neutral: dict) -> tuple[np.ndarray, np.ndarray]:
        """Score rows as given and with `neutral` column overrides, in one model call."""
        if candidates.empty:
            return np.array([]), np.array([])
        neutralized = candidates.copy()
        for column, value in neutral.items():
            neutralized[column] = value
        X = self._prepare_candidates(pd.concat([candidates, neutralized], ignore_index=True))
        probs = self._positive(X)
        n = len(candidates)
        return probs[:n], probs[n:]


def load_scorer(settings, *, classifier_factory: Callable = _default_classifier_factory) -> ChurnRiskScorer:
    """Build the resident scorer from settings; any failure becomes ChurnScorerUnavailable."""
    # TabPFN reads its token from the process environment; .env values only reach settings.
    if settings.tabpfn_token and not os.environ.get("TABPFN_TOKEN"):
        os.environ["TABPFN_TOKEN"] = settings.tabpfn_token
    try:
        return ChurnRiskScorer(settings.churn_scorer_artifact_dir, device=settings.churn_scorer_device,
                               verify_hashes=settings.churn_scorer_verify_hashes,
                               allow_cpu_large_context=settings.churn_scorer_allow_cpu_large_context,
                               classifier_factory=classifier_factory)
    except Exception as exc:
        raise ChurnScorerUnavailable(
            f"trained churn scorer could not load from {settings.churn_scorer_artifact_dir!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def load_mapping(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Verify the churn scorer artifact bundle.")
    parser.add_argument("--artifact-dir", default="artifacts")
    parser.add_argument("--verify", action="store_true", help="check files, schema, hashes (no fit)")
    args = parser.parse_args(argv)
    try:
        bundle = ArtifactBundle(args.artifact_dir, verify_hashes=True)
    except Exception as exc:
        sys.stderr.write(f"churn scorer bundle INVALID: {type(exc).__name__}: {exc}\n")
        raise SystemExit(1) from exc
    tabpfn_version = bundle.metadata.get("environment", {}).get("tabpfn")
    sys.stdout.write(f"churn scorer bundle OK: {bundle.artifact_dir} (tabpfn {tabpfn_version})\n")


if __name__ == "__main__":
    main()
