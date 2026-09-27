"""What-if cutoffs on stored validation scores. Exploration only.

Reads `validation_scores.csv` (with round-trip float parsing) and the policy
cutoff from `policy.json` in the policy directory, and nothing else: no test
result, no model. A what-if cutoff changes only the counts shown here. It never
changes the API decision the result section shows, and it is not a policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from med_ui.config import (
    EXPECTED_CONTRACT_VERSION,
    EXPECTED_POLICY_VERSION,
    EXPECTED_SNAPSHOT_ID,
    EXPLORATION_MAX_FALSE_WARNINGS,
    EXPLORATION_POLICY_FILE,
    EXPLORATION_ROUND_CUTOFFS,
    EXPLORATION_SCORES_FILE,
    TRADEOFF_MAX_FALSE_WARNINGS,
)
from med_ui.presentation import ExpectedBundle


@dataclass(frozen=True)
class ExplorationData:
    email_risk: np.ndarray
    misdirected: np.ndarray
    t_warn: float
    policy_version: str
    model_version: str
    feature_spec_version: str
    subset: str

    @property
    def mistakes(self) -> int:
        return int(self.misdirected.sum())

    @property
    def legitimate(self) -> int:
        return int((~self.misdirected).sum())


def load_exploration(policy_dir: Path) -> ExplorationData:
    policy_dir = Path(policy_dir)
    policy = json.loads((policy_dir / EXPLORATION_POLICY_FILE).read_text(encoding="utf-8"))
    if policy.get("policy_version") != EXPECTED_POLICY_VERSION:
        raise ValueError(f"Local policy {policy.get('policy_version')} is not {EXPECTED_POLICY_VERSION}")
    scores = pd.read_csv(
        policy_dir / EXPLORATION_SCORES_FILE,
        float_precision="round_trip",
        usecols=["draft_id", "email_risk", "misdirected"],
    )
    return ExplorationData(
        email_risk=scores["email_risk"].to_numpy(dtype=np.float64),
        misdirected=scores["misdirected"].astype(bool).to_numpy(),
        t_warn=float(policy["T_warn"]),
        policy_version=str(policy["policy_version"]),
        model_version=str(policy["model_version"]),
        feature_spec_version=str(policy["feature_spec_version"]),
        subset=str(policy["selection"]["subset"]),
    )


def expected_bundle(data: ExplorationData) -> ExpectedBundle:
    """What /ready must report before assessment is enabled: this contract and
    snapshot, and the versions and exact cutoff of the local policy file."""
    return ExpectedBundle(
        contract_version=EXPECTED_CONTRACT_VERSION,
        snapshot_id=EXPECTED_SNAPSHOT_ID,
        model_version=data.model_version,
        feature_spec_version=data.feature_spec_version,
        policy_version=data.policy_version,
        t_warn=data.t_warn,
    )


def counts_at(data: ExplorationData, cutoff: float) -> dict:
    """Validation emails at or above a what-if cutoff (equality counts as a warning, as in the policy)."""
    warned = data.email_risk >= cutoff
    return {
        "cutoff": float(cutoff),
        "warned_mistakes": int((warned & data.misdirected).sum()),
        "mistakes": data.mistakes,
        "false_warnings": int((warned & ~data.misdirected).sum()),
        "legitimate": data.legitimate,
        "is_policy": bool(cutoff == data.t_warn),
    }


def cutoff_options(data: ExplorationData) -> list[float]:
    """Slider stops, ascending: stored scores near the top, the policy cutoff, and a few round values."""
    legitimate = np.sort(data.email_risk[~data.misdirected])[::-1]
    floor = legitimate[min(EXPLORATION_MAX_FALSE_WARNINGS, len(legitimate) - 1)] if len(legitimate) else 0.0
    near = data.email_risk[data.email_risk > floor]
    options = set(float(value) for value in near) | {data.t_warn} | set(EXPLORATION_ROUND_CUTOFFS)
    return sorted(options)


def tradeoff_rows(data: ExplorationData) -> list[dict]:
    """The policy cutoff, then each lower stored score where the counts change, until false warnings pass the table limit."""
    rows = [counts_at(data, data.t_warn)]
    for value in sorted(set(float(item) for item in data.email_risk[data.email_risk < data.t_warn]), reverse=True):
        row = counts_at(data, value)
        if row["false_warnings"] > TRADEOFF_MAX_FALSE_WARNINGS:
            break
        previous = rows[-1]
        if (row["warned_mistakes"], row["false_warnings"]) != (previous["warned_mistakes"], previous["false_warnings"]):
            rows.append(row)
    return rows


def position_of(data: ExplorationData, email_risk: float) -> dict:
    """How many validation emails score at or above a draft's email risk score."""
    at_or_above = data.email_risk >= email_risk
    return {
        "email_risk": float(email_risk),
        "mistakes_at_or_above": int((at_or_above & data.misdirected).sum()),
        "legitimate_at_or_above": int((at_or_above & ~data.misdirected).sum()),
        "mistakes": data.mistakes,
        "legitimate": data.legitimate,
    }


def exploration_title(data: ExplorationData) -> str:
    return f"Threshold exploration on validation data ({data.subset}), what-if only"


def exploration_notes(data: ExplorationData) -> list[str]:
    return [
        f"Default policy {data.policy_version}: T_warn = {data.t_warn!r}. Assessment is enabled only when the service reports this same bundle and cutoff.",
        "A what-if cutoff changes only the counts in this section. It does not change the decision above and is not a policy.",
        f"Counts come from the stored {data.subset} scores, the same subset that chose T_warn, so they are not independent evidence. "
        "The warning budget is recorded as insufficient evidence.",
    ]


def counts_sentence(row: dict) -> str:
    label = "Default policy cutoff" if row["is_policy"] else "What-if cutoff"
    return (
        f"{label} {row['cutoff']!r}: {row['warned_mistakes']} of {row['mistakes']} validation mistakes warned, "
        f"{row['false_warnings']} of {row['legitimate']} legitimate validation emails warned (false warnings)."
    )


def position_sentence(position: dict) -> str:
    return (
        f"On validation, {position['legitimate_at_or_above']} of {position['legitimate']} legitimate and "
        f"{position['mistakes_at_or_above']} of {position['mistakes']} misdirected emails score at or above "
        f"this draft's email risk score ({position['email_risk']!r})."
    )
