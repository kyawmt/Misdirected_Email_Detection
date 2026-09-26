"""Load the frozen bundle and the one context snapshot at startup.

Nothing here fits. The text transformer is loaded from its saved file and
bound to the history index once. The model and policy come through
`med_policy.decision.load_bundle`, which checks versions and checksums.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from med_data.io import read_dataset, verify_files
from med_features.profiles import directory_from_dataset, history_index_from_dataset
from med_features.text_model import FittedText
from med_models.data import verify_feature_artifact
from med_policy.decision import PolicyBundle, load_bundle
from med_api.version import DEFAULT_PATHS, ORGANIZATION_DOMAIN, SNAPSHOT_ID


@dataclass(frozen=True)
class ApiPaths:
    policy: Path
    model: Path
    features: Path
    data: Path
    feedback: Path

    @classmethod
    def from_env(cls, root: Path | None = None) -> "ApiPaths":
        base = Path(root) if root else Path(os.environ.get("MED_API_ROOT", "."))

        def pick(name: str, default) -> Path:
            value = os.environ.get(name)
            return Path(value) if value else base / default

        return cls(
            policy=pick("MED_API_POLICY", DEFAULT_PATHS["policy"]),
            model=pick("MED_API_MODEL", DEFAULT_PATHS["model"]),
            features=pick("MED_API_FEATURES", DEFAULT_PATHS["features"]),
            data=pick("MED_API_DATA", DEFAULT_PATHS["data"]),
            feedback=pick("MED_API_FEEDBACK", "var/feedback.jsonl"),
        )


@dataclass
class ScoringContext:
    bundle: PolicyBundle
    transformer: FittedText
    directory: object
    history: object
    address_index: dict[str, str]
    internal_ids: frozenset[str]
    snapshot_id: str
    load_seconds: float

    @property
    def versions(self) -> dict:
        return self.bundle.versions


def load_context(paths: ApiPaths) -> ScoringContext:
    """Load everything once. Raises on any missing or mismatched artifact."""
    started = time.perf_counter()
    verify_feature_artifact(paths.features)
    verify_files(paths.data)
    dataset = read_dataset(paths.data)
    if dataset.summary["dataset_version"] != SNAPSHOT_ID:
        raise ValueError(f"Snapshot {dataset.summary['dataset_version']} is not {SNAPSHOT_ID}")
    bundle = load_bundle(paths.policy, paths.model, paths.features / "artifact_manifest.json")
    transformer = FittedText.load(paths.features / "text_transformer.joblib")
    directory = directory_from_dataset(dataset)
    history = history_index_from_dataset(dataset)
    history.bind(transformer)
    contacts = dataset.contacts
    address_index = {
        str(address).strip().casefold(): str(contact_id)
        for address, contact_id in zip(contacts["email_address"], contacts["contact_id"], strict=True)
    }
    internal = contacts.loc[
        contacts["is_internal"].astype(bool) & (contacts["domain"].astype(str) == ORGANIZATION_DOMAIN), "contact_id"
    ]
    return ScoringContext(
        bundle=bundle,
        transformer=transformer,
        directory=directory,
        history=history,
        address_index=address_index,
        internal_ids=frozenset(str(item) for item in internal),
        snapshot_id=SNAPSHOT_ID,
        load_seconds=time.perf_counter() - started,
    )
