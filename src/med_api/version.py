"""API contract constants. Change API_CONTRACT_VERSION when the request or response shape changes."""

import os

API_CONTRACT_VERSION = "med-api-v1"
SNAPSHOT_ID = "med-synth-v2"
ORGANIZATION_DOMAIN = "demo.example"
MODE = "simulation"

MIN_RECIPIENTS = 1
MAX_RECIPIENTS = 20
MAX_SUBJECT_CHARS = 500
MAX_BODY_CHARS = 20_000

# Seconds from a normalized request to assess_draft returning. Override with
# MED_API_SCORING_TIMEOUT_SECONDS for local experiments.
DEFAULT_SCORING_TIMEOUT_SECONDS = 2.0


def scoring_timeout_seconds() -> float:
    raw = os.environ.get("MED_API_SCORING_TIMEOUT_SECONDS")
    return float(raw) if raw else DEFAULT_SCORING_TIMEOUT_SECONDS
