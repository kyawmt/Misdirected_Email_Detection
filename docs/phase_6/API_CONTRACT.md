# Phase 6 — API contract

Contract version `med-api-v1`. The service is a simulation over fictional `.example` mail. Every number it returns is a **risk score**, not a probability.

## Endpoints

| Method and path | Role | Success |
| --- | --- | --- |
| `GET /health` | The process is up. It does not prove the bundle loaded. | 200 |
| `GET /ready` | The bundle loaded and the snapshot is resolvable. Returns versions and `T_warn`. | 200, else 503 |
| `POST /assess` | One simulated assessment. | 200 assessed, 422 `invalid_input`, 503 `unavailable` |
| `POST /feedback` | Store a reviewed label for an earlier assessment. Does not score or train. | 200, else 422 |

## Assessment request

| Field | Required | Rule |
| --- | --- | --- |
| `draft_timestamp` | yes | ISO 8601 with a timezone. A naive timestamp is `invalid_input`. It is the historical cutoff. |
| `sender` | yes | Address string or `{address, display_name}`. Must resolve to an internal `demo.example` contact. |
| `to`, `cc`, `bcc` | yes | Lists, each may be empty. Entries are address strings or `{address, display_name}`. 1 to 20 unique addresses in total. |
| `subject` | yes | String, may be empty, at most 500 characters. |
| `body` | yes | Plain text, may be empty, at most 20,000 characters. No HTML parsing. |
| `context_snapshot_id` | yes | Only `med-synth-v4` is accepted. The server resolves it; the caller does not upload history. |
| `draft_reference` | no | Caller correlation label, returned unchanged. Not a feature. |

Accepted top-level fields: `bcc`, `body`, `cc`, `context_snapshot_id`, `draft_reference`, `draft_timestamp`, `sender`, `subject`, `to`. Any other field is `invalid_input`. A field whose name contains any of `label`, `intended`, `scenario`, `split`, `subset`, `family`, `score`, `risk`, `stipulation`, `withheld`, `counterfactual`, `variant` is rejected by name, at any depth, and its value is never read.

Addresses follow assumption A7: surrounding whitespace is trimmed, matching is case-insensitive on the whole address, only ASCII `local@domain` with a domain of `example` or ending in `.example` is accepted, and the same address across To, Cc, and Bcc becomes one recipient that keeps every role. The first non-empty display name is kept. Recipient order is first appearance. Limits count characters and nothing is truncated.

## Assessed response

| Field | Meaning |
| --- | --- |
| `request_id` | Server-generated for every request. |
| `draft_reference` | The caller's label, when one was sent. |
| `contract_version` | `med-api-v1`. |
| `status` | `assessed`. |
| `mode` | `simulation`. |
| `decision` | `allow` or `warn`. Blocking is disabled, so `block` is never returned. |
| `email_risk_score` | Maximum recipient risk score. |
| `flagged_recipients` | Every address whose risk score is at or above `T_warn`. |
| `recipients` | One entry per unique address: `address`, `display_name`, `roles`, `risk_score`, `flagged`, `reason_codes`, `evidence_limitations`. |
| `explanation` | Short sentences, including whether draft-text similarity was an input of the served model. |
| `provenance` | Model, feature-spec, and policy versions, `T_warn`, `blocking_enabled: false`, snapshot id, effective cutoff, and the history rule. |
| `duration_ms` | Handler time for this assessment. |

## Codes

Context codes and limitations are read from the feature row. They do not change the decision and are not read from model coefficients. `CONTENT_RELATIONSHIP_MISMATCH` is a reason tied to the model: it is emitted on a flagged recipient only when its content cosine was observed, is below the typical train value (the mean observed cosine on train, from the feature quality report), and raising only that value to the typical one would drop the recipient's risk score below `T_warn`. The check rescores the frozen model on that one changed row; it never changes the decision.

| Code | Kind | Emitted when | Text |
| --- | --- | --- | --- |
| `LIMITED_RELATIONSHIP_HISTORY` | evidence limitation, any recipient | `recipient_novel_to_sender` is 1 or `pair_recency_observed` is 0 | Little or no prior communication is available; an evidence limitation, not a verdict. |
| `LIMITED_TEXT` | evidence limitation, any recipient | draft text empty, short, or out of vocabulary | Little text is available for content assessment; an evidence limitation. |
| `EXTERNAL_RECIPIENT` | context, flagged recipient only | `recipient_is_internal` is 0 | The address is outside the fictional organization; context, not proof of a mistake. |
| `LOOKALIKE_CONTACT_CONTEXT` | context, flagged recipient only | `near_name_count` is at least 1 | A similar contact identity and other context warrant review; similarity alone is not a mistake finding. |
| `CONTENT_RELATIONSHIP_MISMATCH` | reason, flagged recipient only | observed content cosine below the typical train value, and a rescore with only that value raised to typical falls below `T_warn` | This draft differs from prior topics exchanged with this recipient. |
| `UNUSUAL_RECIPIENT_COMBINATION` | context, flagged recipient only | co-recipient support applies and the partner fraction is 0 | These addressees have little support as a group in the available prior communication. |

## Feedback request

`{request_id, recipient, label}` with `label` of `intended` or `unintended`. The request id must be an assessment this process returned, and the recipient must have been on it. Otherwise the response is `invalid_input` and nothing is written. Accepted feedback appends one JSON line (request id, contact id, label, versions, time) to a local, gitignored file. `/assess` never reads it, and it never changes the model, the policy, or the cutoff.

## Examples

These bodies come from live calls on fictional validation drafts, chosen by rule from the policy's validation table. `d003028` is the warned validation mistake with the lowest email risk score; `d005962` is the allowed routine draft at the median score.

### Warn request (`d003028`)

```json
{
  "draft_timestamp": "2025-05-01T12:56:10Z",
  "sender": {
    "address": "maya@demo.example",
    "display_name": "Maya Okonkwo"
  },
  "to": [
    {
      "address": "reese.ibarra@demo.example",
      "display_name": "Reese Ibarra"
    }
  ],
  "cc": [
    {
      "address": "lee@vendor.example",
      "display_name": "Lee Park"
    }
  ],
  "bcc": [],
  "subject": "Cost center forecast 2025-05-01",
  "body": "Hi Reese,\n\nAttached in prose: the cost center forecast for 2025-05-01. Ticket T-102085 flags one variance in the project budget. Please confirm the figure before the review.\n\nThanks,\nMaya\nRef: m102085",
  "context_snapshot_id": "med-synth-v4",
  "draft_reference": "fixture-d003028"
}
```

### Warn response (HTTP 200)

```json
{
  "request_id": "req_example",
  "contract_version": "med-api-v1",
  "status": "assessed",
  "mode": "simulation",
  "decision": "warn",
  "email_risk_score": 0.9996767050340489,
  "flagged_recipients": [
    "lee@vendor.example"
  ],
  "recipients": [
    {
      "address": "reese.ibarra@demo.example",
      "display_name": "Reese Ibarra",
      "roles": [
        "to"
      ],
      "risk_score": 0.0009664412467289453,
      "flagged": false,
      "reason_codes": [],
      "evidence_limitations": []
    },
    {
      "address": "lee@vendor.example",
      "display_name": "Lee Park",
      "roles": [
        "cc"
      ],
      "risk_score": 0.9996767050340489,
      "flagged": true,
      "reason_codes": [
        {
          "code": "EXTERNAL_RECIPIENT",
          "text": "The address is outside the fictional organization; context, not proof of a mistake."
        },
        {
          "code": "UNUSUAL_RECIPIENT_COMBINATION",
          "text": "These addressees have little support as a group in the available prior communication."
        },
        {
          "code": "CONTENT_RELATIONSHIP_MISMATCH",
          "text": "This draft differs from prior topics exchanged with this recipient."
        }
      ],
      "evidence_limitations": []
    }
  ],
  "explanation": [
    "Risk scores come from sender-recipient history, recency, co-recipient support, and contact similarity. Draft-text similarity to earlier mail with each recipient was also an input to this model.",
    "Scores are risk scores, not probabilities.",
    "Warn asks the sender to review the flagged recipients. It is not a finding about the sender's intent."
  ],
  "provenance": {
    "model_version": "med-model-v2",
    "feature_spec_version": "med-features-v2",
    "policy_version": "med-policy-v2",
    "T_warn": 0.9996767050340489,
    "blocking_enabled": false,
    "snapshot_id": "med-synth-v4",
    "effective_cutoff": "2025-05-01T12:56:10.000000Z",
    "history_rule": "sent mail strictly earlier than the cutoff"
  },
  "draft_reference": "fixture-d003028",
  "duration_ms": "<measured>"
}
```

### Allow response for `d005962` (HTTP 200)

```json
{
  "request_id": "req_example",
  "contract_version": "med-api-v1",
  "status": "assessed",
  "mode": "simulation",
  "decision": "allow",
  "email_risk_score": 7.749000663705964e-05,
  "flagged_recipients": [],
  "recipients": [
    {
      "address": "oakley.ibarra@demo.example",
      "display_name": "Oakley Ibarra",
      "roles": [
        "to"
      ],
      "risk_score": 7.749000663705964e-05,
      "flagged": false,
      "reason_codes": [],
      "evidence_limitations": []
    }
  ],
  "explanation": [
    "Risk scores come from sender-recipient history, recency, co-recipient support, and contact similarity. Draft-text similarity to earlier mail with each recipient was also an input to this model.",
    "Scores are risk scores, not probabilities.",
    "Allow means no intervention under this policy. It does not guarantee that every recipient is correct."
  ],
  "provenance": {
    "model_version": "med-model-v2",
    "feature_spec_version": "med-features-v2",
    "policy_version": "med-policy-v2",
    "T_warn": 0.9996767050340489,
    "blocking_enabled": false,
    "snapshot_id": "med-synth-v4",
    "effective_cutoff": "2025-07-11T10:19:24.000000Z",
    "history_rule": "sent mail strictly earlier than the cutoff"
  },
  "draft_reference": "fixture-d005962",
  "duration_ms": "<measured>"
}
```

### `invalid_input` response (HTTP 422)

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
  "draft_reference": "fixture-d005962",
  "provenance": {
    "model_version": "med-model-v2",
    "feature_spec_version": "med-features-v2",
    "policy_version": "med-policy-v2",
    "snapshot_id": "med-synth-v4"
  },
  "duration_ms": "<measured>"
}
```

### `unavailable` response (HTTP 503)

```json
{
  "request_id": "req_example",
  "contract_version": "med-api-v1",
  "status": "unable_to_assess",
  "category": "unavailable",
  "message": "A recipient is not in the context snapshot directory",
  "mode": "simulation",
  "decision": null,
  "email_risk_score": null,
  "flagged_recipients": null,
  "recipients": null,
  "draft_reference": "fixture-d005962",
  "provenance": {
    "model_version": "med-model-v2",
    "feature_spec_version": "med-features-v2",
    "policy_version": "med-policy-v2",
    "snapshot_id": "med-synth-v4"
  },
  "duration_ms": "<measured>"
}
```
