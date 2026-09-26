"""API contract constants and the served bundle.

Change API_CONTRACT_VERSION when the request or response shape changes. The
snapshot id and default bundle paths come from `med_policy.version`, so the
API serves whatever bundle the policy package names.
"""

import os

from med_policy.version import (
    ARTIFACT_ROOT,
    DATA_DIR,
    DATASET_VERSION,
    FEATURES_DIR,
    MODEL_PATH,
    POLICY_PATH,
    POLICY_VERSION,
)

API_CONTRACT_VERSION = "med-api-v1"
SNAPSHOT_ID = DATASET_VERSION
ORGANIZATION_DOMAIN = "demo.example"
MODE = "simulation"

MIN_RECIPIENTS = 1
MAX_RECIPIENTS = 20
MAX_SUBJECT_CHARS = 500
MAX_BODY_CHARS = 20_000

# Seconds from a normalized request to assess_draft returning. Override with
# MED_API_SCORING_TIMEOUT_SECONDS for local experiments.
DEFAULT_SCORING_TIMEOUT_SECONDS = 2.0

# Default bundle paths, relative to MED_API_ROOT (the repository root).
DEFAULT_PATHS = {
    "policy": POLICY_PATH,
    "model": MODEL_PATH,
    "features": FEATURES_DIR,
    "data": DATA_DIR,
}
# AC05 latency is keyed by the served policy bundle, not by the contract
# version, so a new bundle never overwrites an earlier measurement.
LATENCY_PATH = ARTIFACT_ROOT / "med-api-latency" / POLICY_VERSION / "latency.json"
DOCS_DIR = "docs/phase_6"


def scoring_timeout_seconds() -> float:
    raw = os.environ.get("MED_API_SCORING_TIMEOUT_SECONDS")
    return float(raw) if raw else DEFAULT_SCORING_TIMEOUT_SECONDS
