# Phase 6 — Scoring flow

Served bundle: dataset snapshot `med-synth-v4`, features `med-features-v2`, model `med-model-v2` (`logistic_all_balanced`), policy `med-policy-v2`, contract `med-api-v1`.

## Startup

At startup the app loads, once and without fitting anything:

1. the feature artifact manifest, with every file checksum verified
2. the `med-synth-v4` tables, with dataset checksums verified
3. the model and the policy through `med_policy.decision.load_bundle`, which refuses a version, run-name, or checksum mismatch
4. the saved text transformer
5. the contact directory and the sent-mail history index; the transformer is bound to the index once

`/ready` returns 503 until that succeeds. `/health` answers either way. If the load fails, every `/assess` returns `unavailable`.

## Request

1. Parse the JSON body. Reject label, scenario, split, family, and score fields by name, and any field outside the contract.
2. Normalize (A7): timestamp with timezone, `.example` addresses, merge repeated addresses across roles, limits.
3. Resolve the snapshot id (`med-synth-v4` only), the sender (internal contact), and every recipient in the directory.
4. Build one `DraftQuery`. The family exclusion is empty, because a client draft has no family. A non-empty body's hash is excluded from history so the draft is not its own earlier mail. History is sent mail strictly earlier than the cutoff.
5. Call `med_policy.decision.assess_draft` under the scoring timeout. It runs `transform_draft`, the frozen model, and the policy. The API does not reimplement the cutoff, the maximum, or the model.
6. Map the result to the response. Reason codes and limitations are read from the same feature rows. They do not change the decision.

`T_warn` is loaded from `policy.json`. It is not reselected, and it is not recomputed from `validation_scores.csv`.

## What the service does not change

- The service serves the frozen cutoff. On the one `test_product_like` pass it warned on 9 of 30 misdirected emails with 0 false interventions on 5970 legitimate emails; the exact upper 95% bound, 0.62 per 1,000, is within the budget of 1. That is a simulation result.
- Scenarios never warned in the frozen test subsets: S01, S04, S11. The API does not change that.
- A well-formed address that is not in the snapshot directory, such as a typo, is `unavailable`, not a warning. Changing that is a contract decision.
- No rule warns because a recipient is new, external, a lookalike, or off-topic.

## Latency (AC05)

Measured once with `python -m med_api latency` for policy bundle `med-policy-v2`: 4000 `POST /assess` calls on `validation_product_like` requests after 20 unmeasured warm-up calls, concurrency 1. Boundary: test client sends POST /assess until the response body is complete, in process, no network. This contains assumption A10's boundary (backend receipt to response preparation) and adds only the in-process client and ASGI hop. The record is keyed by the policy bundle and is never overwritten.

Workload: every validation_product_like draft, in one permutation with seed 20260926, fixed before timing. Warm-up: the first 20 drafts of that permutation, called once each and not timed; they are measured again in order.

| Measure | Value |
| --- | --- |
| Client p50 | 26.84 ms |
| Client p95 | 57.04 ms |
| Client p99 | 74.43 ms |
| Client max | 445.79 ms |
| Server-side p50 / p95 / max | 26.06 / 56.28 / 443.53 ms |
| Target | p95 below 300 ms |
| AC05 | **met** |
| Cold start | 7.95 s (app creation and startup: dataset read with checksums, bundle load with checksum checks, transformer load, directory and history index, history vectorization) |
| Statuses | assessed: 4000 |
| Recipients per request | 1: 3600, 2: 100, 3: 69, 4: 195, 5: 33, 6: 3 |
| Month of draft | 2025-03: 45, 2025-04: 813, 2025-05: 806, 2025-06: 759, 2025-07: 823, 2025-08: 754 |
| Sender history (earlier sent messages) | 0-999: 52, 1000-2499: 98, 2500-4999: 27, 5000-9999: 19, 10000-19999: 0, 20000-39999: 0, 40000+: 3804; quartiles 48762 / 52897 / 57033, max 61221 |
| Hardware and OS | macOS-27.0-arm64-arm-64bit, arm64, 10 CPUs |
| Versions | contract_version med-api-v1, model_version med-model-v2, feature_spec_version med-features-v2, policy_version med-policy-v2, snapshot_id med-synth-v4, python 3.11.14, fastapi 0.141.1, scikit_learn 1.9.1, numpy 2.4.6 |

AC05 is recorded as **met** on the client-side p95 of 57.04 ms, on this machine only. The model and policy were not changed to improve it. The content-cosine centroid is built from one sparse slice of the history matrix per recipient, not one row read at a time; that change leaves every feature value identical.

## Parity with the frozen validation scores

During the same run, 4000 of 4000 API decisions matched the `warned` column of `validation_scores.csv`. The largest email risk score difference was 3.89e-15. Feature CSVs are lossless, so the remaining difference is summation order in the model, and the policy selection already required identical decisions on every validation draft.

`d003028` is the validation draft whose score set `T_warn` (0.9996767050340489). Through the API it scores 0.9996767050340489 (+0.0e+00 from the cutoff) and returns `warn`.
