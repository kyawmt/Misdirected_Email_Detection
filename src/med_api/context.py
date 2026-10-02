"""Load the frozen bundle and the one context snapshot at startup.

Nothing here fits. The text transformer is loaded from its saved file and
bound to the history index once. The model and policy come through
`med_policy.decision.load_bundle`, which checks versions, checksums, the cutoff
range, and the policy file's own digest.

The dataset directory is read in two steps: the SHA-256 of every file in its
manifest is checked, then only the contact directory and the sent-mail history
(`contacts.csv`, `messages.csv`, `message_recipients.csv`) are parsed. No draft,
label, split, or feedback table is parsed.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from med_data.io import read_serving_tables
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
    content_reference: float | None = None

    @property
    def versions(self) -> dict:
        return self.bundle.versions


def load_context(paths: ApiPaths) -> ScoringContext:
    """Load everything once. Raises on any missing or mismatched artifact."""
    started = time.perf_counter()
    verify_feature_artifact(paths.features)
    # The policy and model are checked before the large dataset read, so a refused bundle fails fast.
    bundle = load_bundle(paths.policy, paths.model, paths.features / "artifact_manifest.json")
    tables = read_serving_tables(paths.data)
    if tables.dataset_version != SNAPSHOT_ID:
        raise ValueError(f"Snapshot {tables.dataset_version} is not {SNAPSHOT_ID}")
    transformer = FittedText.load(paths.features / "text_transformer.joblib")
    directory = directory_from_dataset(tables)
    history = history_index_from_dataset(tables)
    history.bind(transformer)
    contacts = tables.contacts
    address_index = {
        str(address).strip().casefold(): str(contact_id)
        for address, contact_id in zip(contacts["email_address"], contacts["contact_id"], strict=True)
    }
    internal = contacts.loc[
        contacts["is_internal"].astype(bool) & (contacts["domain"].astype(str) == ORGANIZATION_DOMAIN), "contact_id"
    ]
    return ScoringContext(
        content_reference=content_reference(paths.features),
        bundle=bundle,
        transformer=transformer,
        directory=directory,
        history=history,
        address_index=address_index,
        internal_ids=frozenset(str(item) for item in internal),
        snapshot_id=SNAPSHOT_ID,
        load_seconds=time.perf_counter() - started,
    )


def content_reference(features_dir: Path) -> float | None:
    """Mean observed content cosine on train rows, from the published feature quality report.

    Label-free and fit on train only. It is the "typical content" value the
    content reason code compares against. None when the report lacks it.
    """
    path = Path(features_dir) / "quality_report.json"
    if not path.exists():
        return None
    stats = json.loads(path.read_text(encoding="utf-8"))["subsets"]["train"]["features"]["content_cosine"]
    value = stats.get("mean")
    return float(value) if value is not None else None
