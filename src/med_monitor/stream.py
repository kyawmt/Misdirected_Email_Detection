"""The replay plan: which validation drafts make up each window.

Traffic is the `validation_product_like` subset in send-time order, cut into
consecutive windows. In shifted windows a seeded share of ordinary routine
drafts is replaced by copies of legitimate first-contact validation drafts (a
new partner or collaborator wave). The plan lists draft ids only; addresses,
subjects, and bodies are read from the validation tables when the plan runs.

Scenario and variant fields are used here to build the simulated traffic. They
are never sent to the API and never used as monitored inputs.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from med_monitor.data import DataError, FrozenRowError
from med_monitor.version import (
    CURRENT_WINDOWS,
    FIRST_CONTACT_VARIANTS,
    FROZEN_SUBSETS,
    MONITOR_VERSION,
    N_WINDOWS,
    PLAN_SEED,
    REFERENCE_WINDOWS,
    REPLACEABLE_SCENARIO,
    SHIFT_SCHEDULE,
    TRAFFIC_SUBSET,
    VALIDATION_SUBSETS,
    WINDOW_EMAILS,
)


def build_plan(structure: pd.DataFrame) -> dict:
    """Build the plan from validation structure rows. Deterministic for a given seed."""
    unknown = set(structure["subset"]) - set(VALIDATION_SUBSETS)
    if unknown:
        raise FrozenRowError(f"Structure rows include non-validation subsets: {sorted(unknown)}")
    traffic = structure.loc[structure["subset"] == TRAFFIC_SUBSET].sort_values(["sent_at", "draft_id"], kind="mergesort")
    if len(traffic) != N_WINDOWS * WINDOW_EMAILS:
        raise DataError(f"{TRAFFIC_SUBSET} has {len(traffic)} drafts; the plan needs {N_WINDOWS * WINDOW_EMAILS}")
    pool = structure.loc[structure["scenario_variant"].isin(FIRST_CONTACT_VARIANTS)].sort_values("draft_id")
    pool_ids = pool["draft_id"].tolist()
    if not pool_ids:
        raise DataError("No legitimate first-contact validation drafts for the shift pool")
    routine = traffic.loc[traffic["scenario_id"] == REPLACEABLE_SCENARIO, "draft_id"]
    if routine.empty:
        raise DataError("No routine draft to base the failure probes on")
    windows = []
    for window in range(1, N_WINDOWS + 1):
        chunk = traffic.iloc[(window - 1) * WINDOW_EMAILS : window * WINDOW_EMAILS]
        ids = chunk["draft_id"].tolist()
        share = float(SHIFT_SCHEDULE.get(window, 0.0))
        count = int(round(share * WINDOW_EMAILS))
        injected = []
        if count:
            rng = np.random.default_rng([PLAN_SEED, window])
            candidates = np.flatnonzero((chunk["scenario_id"] == REPLACEABLE_SCENARIO).to_numpy())
            positions = np.sort(rng.choice(candidates, size=count, replace=False))
            drawn: list[str] = []
            while len(drawn) < count:
                drawn.extend(rng.permutation(pool_ids).tolist())
            for position, draft_id in zip(positions.tolist(), drawn[:count], strict=True):
                ids[position] = draft_id
                injected.append({"position": int(position), "draft_id": draft_id})
        windows.append(
            {
                "window": window,
                "role": "reference" if window in REFERENCE_WINDOWS else "current",
                "emails": len(ids),
                "first_sent_at": chunk["sent_at"].iloc[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_sent_at": chunk["sent_at"].iloc[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "injected_share": share,
                "injected_emails": len(injected),
                "injected": injected,
                "draft_ids": ids,
            }
        )
    plan = {
        "monitor_version": MONITOR_VERSION,
        "seed": PLAN_SEED,
        "traffic_subset": TRAFFIC_SUBSET,
        "window_emails": WINDOW_EMAILS,
        "reference_windows": list(REFERENCE_WINDOWS),
        "current_windows": list(CURRENT_WINDOWS),
        "shift_schedule": {str(key): value for key, value in sorted(SHIFT_SCHEDULE.items())},
        "shift": {
            "kind": "new partner or collaborator wave: legitimate first contacts replace routine drafts",
            "pool_variants": list(FIRST_CONTACT_VARIANTS),
            "pool_subsets": list(VALIDATION_SUBSETS),
            "pool_drafts": len(pool_ids),
            "pool_draft_ids": pool_ids,
            "replaced_scenario": REPLACEABLE_SCENARIO,
        },
        "probe_draft_id": str(routine.iloc[0]),
        "windows": windows,
    }
    plan["checksum_sha256"] = plan_checksum(plan)
    return plan


def plan_checksum(plan: dict) -> str:
    digest = hashlib.sha256()
    for window in plan["windows"]:
        digest.update(f"window {window['window']}\n".encode())
        digest.update("\n".join(window["draft_ids"]).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def plan_ids(plan: dict) -> set[str]:
    ids = set(plan["shift"]["pool_draft_ids"]) | {plan["probe_draft_id"]}
    for window in plan["windows"]:
        ids |= set(window["draft_ids"])
    return ids


def check_plan(plan: dict, subset_of: dict[str, str]) -> None:
    """Every planned draft is a validation draft; none is frozen."""
    for draft_id in sorted(plan_ids(plan)):
        subset = subset_of.get(draft_id)
        if subset in FROZEN_SUBSETS:
            raise FrozenRowError(f"Plan includes {draft_id} from frozen subset {subset}")
        if subset not in VALIDATION_SUBSETS:
            raise DataError(f"Plan includes {draft_id} with subset {subset}")
    if plan_checksum(plan) != plan.get("checksum_sha256"):
        raise DataError("The plan's checksum does not match its draft lists")
    for window in plan["windows"]:
        if window["emails"] != len(window["draft_ids"]):
            raise DataError(f"Window {window['window']} count does not match its draft list")
