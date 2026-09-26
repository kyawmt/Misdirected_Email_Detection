# Phase 6 — Error behavior

Both failure categories are **unable to assess** (assumption A9). `decision`, `email_risk_score`, `recipients`, and `flagged_recipients` are null. The service never returns `allow` for a failure, and never returns an empty flagged list as if the assessment succeeded. A whole request fails if any recipient cannot be assessed.

| Category | HTTP | When |
| --- | --- | --- |
| `invalid_input` | 422 | Malformed JSON or address, non-`.example` domain, non-ASCII address, timestamp without a timezone, 0 or more than 20 unique recipients, subject over 500 or body over 20,000 characters, sender not an internal `demo.example` address, unsupported fields, or a label, scenario, split, family, or score field. |
| `unavailable` | 503 | Unknown snapshot id, sender or recipient address well formed but not in the directory, bundle failed to load, version or checksum mismatch, `FeatureError` or `ModelError` while scoring, a non-finite risk score, or the scoring timeout. |

A failure body carries the request id, the category, a short message, and versions only when they are known. If the bundle did not load, no model or policy version is reported.

No history is not a failure. A sender or recipient with no earlier mail is assessed with the existing feature fallback and may carry `LIMITED_RELATIONSHIP_HISTORY`. It is not forced to allow or warn.

## Timeout

The scoring timeout is 2 seconds, overridable with `MED_API_SCORING_TIMEOUT_SECONDS`. It starts when the handler has a normalized request and ends when `assess_draft` returns. On timeout the response is `unavailable` with no partial decision. The scoring thread is not interrupted; its late result is discarded.

## Logging

One JSON log line per assessment on logger `med_api`, with only these fields: `event`, `request_id`, `status`, `category`, `decision`, `duration_ms`, `contract_version`, `model_version`, `feature_spec_version`, `policy_version`, `recipient_count`, `flagged_count`. Subject, body, display names, email addresses, and recipient lists are never logged. Feedback lines store the contact id, not the address.

## Examples

Unknown snapshot (HTTP 503):

```json
{
  "request_id": "req_example",
  "contract_version": "med-api-v1",
  "status": "unable_to_assess",
  "category": "unavailable",
  "message": "The context snapshot is not available",
  "mode": "simulation",
  "decision": null,
  "email_risk_score": null,
  "flagged_recipients": null,
  "recipients": null,
  "draft_reference": "fixture-d001083",
  "provenance": {
    "model_version": "med-model-v1",
    "feature_spec_version": "med-features-v1",
    "policy_version": "med-policy-v1",
    "snapshot_id": "med-synth-v2"
  },
  "duration_ms": "<measured>"
}
```

Malformed recipient address (HTTP 422):

```json
{
  "request_id": "req_example",
  "contract_version": "med-api-v1",
  "status": "unable_to_assess",
  "category": "invalid_input",
  "message": "An address is malformed",
  "mode": "simulation",
  "decision": null,
  "email_risk_score": null,
  "flagged_recipients": null,
  "recipients": null,
  "draft_reference": "fixture-d001083",
  "provenance": {
    "model_version": "med-model-v1",
    "feature_spec_version": "med-features-v1",
    "policy_version": "med-policy-v1",
    "snapshot_id": "med-synth-v2"
  },
  "duration_ms": "<measured>"
}
```
