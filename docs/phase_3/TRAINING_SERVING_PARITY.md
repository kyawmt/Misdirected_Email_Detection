# Phase 3 — Training and serving parity

Feature specification: `med-features-v2`.

Training rows and a later single-draft score use one row builder, one feature order, and one fitted text transformer. The checks below are implemented in `tests/test_phase3.py`. They use small fixtures for behavior and the published dataset only for integrity: history identity, train-only fitting, and agreement between the index and a scoring view. They do not inspect frozen-test feature distributions.

## Same matrix

- `transform_drafts` on a list of queries equals the concatenation of `transform_draft` on each query.
- Calling the transform twice on the same index and transformer returns the same frame.
- Saving `text_transformer.joblib` and loading it, then binding a new index, returns the same frame. The load path checks the specification version and the preprocessor config. It does not call `fit`.
- A scoring view's history, passed through `EventHistory`, matches the index path for the same draft. The view carries no labels. The index path applies the family and body-hash exclusions itself.
- The published feature CSVs are lossless: for the first, middle, and last draft of each exported subset, a fresh in-memory transform equals the stored rows bit for bit when read with `read_features`.
- The vectorized content-cosine centroid equals an explicit per-row mean on a fixture, skipping rows with no vocabulary term.

## Same history rules

- A message at the draft timestamp is excluded. A later message is excluded.
- A message in the draft's family is excluded even when its timestamp is earlier.
- An earlier message in another family is excluded when its non-empty body hash equals the draft body. A different draft body keeps that message.
- The 28-day window includes a message at exactly `cutoff - 28 days` and excludes a message one second earlier.
- Fixture counts, recency, span, and co-recipient fractions are asserted as literals, not by calling the feature code a second way.
- On the published dataset, the index's visible message ids equal `visible_history` for sampled train and validation drafts.

## Same preprocessing

- `Ref` / `Ack` ids, ticket ids, and ISO dates are removed before TF-IDF. The tokens `ref` and `ack` are dropped.
- The official vocabulary matches a fit on `training_documents` alone.
- Adding a validation message to that document list changes the vocabulary or the IDF weights. The published transformer does not use that wider fit.
- A term that appears only once in the fit corpus is dropped (`min_df = 2`). A term that appears only outside the fit corpus is absent.
- Two texts that differ only by a `Ref:` id produce cosine 1 when that text is the sole pair history. The body hash still distinguishes them, so the copy rule does not have to keep the raw strings identical.

## Leakage controls that are not features

- Feature names are disjoint from the Phase 2 model-input denylist, from role names, and from message and draft ids.
- Replacing scenario, split, subset, withheld contact, label, and role on a fixture leaves the matrix unchanged.
- Similarity candidates are the visible directory minus the recipient. A contact whose directory time is after the cutoff is omitted, even if the display name is identical. A directory that contains only the recipient yields `contact_similarity_observed = 0`, not a self-similarity of 1.
- The quality report and the feature build refuse `test_product_like` and `test_diagnostic`. The report may join scenario and label columns only after the matrix exists, and only for train and validation.

## Fallback contract

`validate_feature_frame` rejects missing or non-finite values, negative counts, indicators outside `{0, 1}`, and fallback mismatches. In particular:

- unobserved recency is exactly 3650 days, and observed recency is strictly positive
- a sender with no outbound mail has span 0 and rate 0
- recipient novelty matches a zero outbound pair count
- single-recipient drafts do not report a measured co-support fraction
- unobserved cosine is 0, and an observed cosine requires in-vocabulary draft text and at least one pair text message
- an empty draft is not marked out of vocabulary

Serving code that loads `med-features-v2` should run this check on a scored frame when a regression suite is added. A failed check is a broken transform, not a low-risk draft.

## What parity does not cover

This phase does not serve an API, so there is no network timeout, request id, or `unable_to_assess` payload yet. `FeatureError` is the in-process signal for an unknown contact or an empty recipient list. Latency is not measured. The frozen test subsets are not compared to a training distribution here.
