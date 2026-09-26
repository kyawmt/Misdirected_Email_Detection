# Phase 6 — Scoring flow

## Startup

At startup the app loads, once and without fitting anything:

1. the feature artifact manifest, with every file checksum verified
2. the `med-synth-v2` tables, with dataset checksums verified
3. the model and the policy through `med_policy.decision.load_bundle`, which refuses a version, run-name, or checksum mismatch
4. the saved text transformer
5. the contact directory and the sent-mail history index; the transformer is bound to the index once

`/ready` returns 503 until that succeeds. `/health` answers either way. If the load fails, every `/assess` returns `unavailable`.

## Request

1. Parse the JSON body. Reject label, scenario, split, family, and score fields by name, and any field outside the contract.
2. Normalize (A7): timestamp with timezone, `.example` addresses, merge repeated addresses across roles, limits.
3. Resolve the snapshot id (`med-synth-v2` only), the sender (internal contact), and every recipient in the directory.
4. Build one `DraftQuery`. The family exclusion is empty, because a client draft has no family. A non-empty body's hash is excluded from history so the draft is not its own earlier mail. History is sent mail strictly earlier than the cutoff.
5. Call `med_policy.decision.assess_draft` under the scoring timeout. It runs `transform_draft`, the frozen logistic model, and the policy. The API does not reimplement the cutoff, the maximum, or the model.
6. Map the result to the response. Reason codes and limitations are read from the same feature rows. They do not change the decision.

`T_warn` is loaded from `policy.json`. It is not reselected, and it is not recomputed from `validation_scores.csv`.

## What the service does not change

- The warning budget is not supported at the required confidence: zero false warnings on 1,990 legitimate test emails still leave an exact upper bound of about 1.85 per 1,000.
- A mistaken first contact scores near 0 and is allowed. A mistyped address that is not in the directory is `unavailable`, not a warning.
- Lookalike replacements (S01) and familiar-recipient, unusual-topic mistakes (S04) are still missed.
- No rule warns because a recipient is new, external, a lookalike, or off-topic.

## Latency (AC05)

Measured once with `python -m med_api latency`: 1000 `POST /assess` calls on `validation_product_like` requests after 20 unmeasured warm-up calls, concurrency 1. Boundary: test client sends POST /assess until the response body is complete, in process, no network. This contains assumption A10's boundary (backend receipt to response preparation) and adds only the in-process client and ASGI hop.

| Measure | Value |
| --- | --- |
| Client p50 | 25.63 ms |
| Client p95 | 345.84 ms |
| Client max | 492.51 ms |
| Server-side p50 / p95 / max | 24.84 / 344.99 / 491.45 ms |
| Target | p95 below 300 ms |
| AC05 | **not met** |
| Cold start | 1.32 s (app creation and startup: dataset read with checksums, bundle load with checksum checks, transformer load, directory and history index, history vectorization) |
| Statuses | assessed: 1000 |
| Recipients per request | 1: 526, 2: 64, 3: 69, 4: 302, 5: 38, 6: 1 |
| Hardware and OS | macOS-27.0-arm64-arm-64bit, arm64, 10 CPUs |
| Versions | contract_version med-api-v1, model_version med-model-v1, feature_spec_version med-features-v1, policy_version med-policy-v1, python 3.11.14, fastapi 0.141.1, scikit_learn 1.9.1, numpy 2.4.6 |

AC05 is recorded as **not met** on the client-side p95 of 345.84 ms, on this machine only. The model and policy were not changed to improve it.

Server-side time is almost all of the client time, so the cost is in scoring, not in HTTP handling. A profile of the slowest request (a four-recipient project update) spends most of its time building the content-cosine history centroid one sparse row at a time, thousands of reads per recipient. The frozen model does not use that feature. Changing how the shared transform computes it belongs to a later phase and must keep batch/single-draft parity.

## Parity with the frozen validation scores

During the same run, 1000 of 1000 API decisions matched the `warned` column of `validation_scores.csv`. The largest email risk score difference was 2.41e-15: the validation table was scored from the published feature CSV, and the API computes features in memory.

`d001019` is the validation draft whose score set `T_warn` (0.13455666515724893). Through the API it scores 0.13455666515725057, 1.6e-15 above the cutoff, and returns `warn`. Equality warns, but a difference of this size means the equality case is decided by floating-point detail. The cutoff was not moved.
