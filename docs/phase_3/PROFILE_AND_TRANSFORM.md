# Phase 3 — Historical profiles and the transform contract

Feature specification: `med-features-v1`.

Batch export and single-draft scoring call the same row builder, `build_rows`. `transform_draft` scores one draft. `transform_drafts` stacks those rows in the order of the queries. Both return the key columns followed by the feature columns in [the catalog](FEATURE_CATALOG.md).

## What a query contains

A `DraftQuery` has the draft id, cutoff time, sender contact id, subject, body, and the addressed recipients as `(contact_id, recipient_order)` pairs. It also has two exclusion controls: an optional family id, and a set of non-empty body hashes. Those controls are not copied onto the feature row.

The query has no role, label, scenario, split, subset, withheld contact, or generator topic. Changing those audit fields does not change the features. Changing To to Bcc does not change the features.

`query_from_dataset` fills the exclusions the way Phase 2 visible history does: drop the draft's family, and drop any non-empty body hash from that family or from the draft body. Empty bodies are not treated as copies. `query_from_scoring_view` does not set exclusions, because a scoring view's history list is already filtered.

Unknown contacts, a draft with no recipients, and a repeated recipient raise `FeatureError`. This phase does not turn that error into an API response. A later scoring service should treat it as unable to assess, not as an allow.

Repeated addresses are merged before this transform runs. The product input rule says to trim whitespace, match fictional addresses without case sensitivity, and merge the same address across To, Cc, and Bcc while keeping every role. That merge belongs to the request normalizer in the later scoring service. `transform_draft` then receives one entry per unique contact. Calling it with the same contact twice is a contract error, not a second recipient.

## Two ways to supply history

The history index is built from sent messages, message recipients, and the contact directory. It stores pair postings and domain postings in time order. For a query it keeps messages with `sent_at` strictly earlier than the cutoff, then drops the family id and the blocked body hashes. A message at the exact cutoff is excluded. A message one second earlier is eligible.

`EventHistory` is the allow-list boundary. It is built from the history already present on a scoring view, or from any prefiltered event list. The row builder asks either source for the same things: outbound positions, inbound positions, timestamps, recipient ids, domains, and TF-IDF rows. Tests require the index path and the scoring-view path to return the same matrix.

The directory profile is separate from the mail index. Similarity candidates are contacts with `directory_visible_from` at or before the cutoff, excluding the recipient. The scoring view does not need to list the whole directory. The profile does.

## Point-in-time profiles

An early draft does not see mail sent after its cutoff. Rebuilding the index after later mail arrives does not change features for a draft whose cutoff is still before that mail. There is no end-of-training count profile.

The text transformer is the exception, and it is explicit. Vocabulary and IDF are fit once on sent mail before the validation window, including warmup. They are not fit again on validation or test text, and they are not refit for each training draft. Centroids still use only pair messages before the draft.

## Updating profiles without refitting

New sent mail can be incorporated by rebuilding the index from the sent-mail tables and calling `transform` on the new texts with the saved vectorizer. Do not call `fit`. Tokens that are outside the frozen vocabulary are ignored. IDF weights stay at the values stored in `text_transformer.joblib`.

The index is derived from the dataset plus that transformer. It is not a second trained model. The published artifact stores the transformer, the schema, the fit metadata, and the train and validation matrices. A process that needs the index builds it again from `data/med-synth-v2` and the saved transformer.

## What the build writes

From the repository root, after the package is installed:

```bash
python -m med_features build --data data/med-synth-v2 --output artifacts/med-features-v1 \
  --quality-markdown docs/phase_3/FEATURE_QUALITY_REPORT.md
```

The command checks the dataset checksums, fits the transformer, and writes recipient rows for `train`, `validation_product_like`, and `validation_diagnostic` only. `test_product_like` and `test_diagnostic` are refused. The transform function itself does not receive a subset name. A later one-time evaluation can call it on a frozen draft. This phase's build does not.

| File | Role |
| --- | --- |
| `text_transformer.joblib` | Fitted vectorizer, preprocessor config, and fit scope. Loading it does not refit. |
| `feature_schema.json` | Column order, dtypes, and fallback rules. |
| `fit_metadata.json` | Dataset version, dataset file checksums, fit scope, and row counts. |
| `features_train.csv` | Training recipient rows. |
| `features_validation_product_like.csv` | Product-like validation rows. |
| `features_validation_diagnostic.csv` | Diagnostic validation rows. |
| `quality_report.json` | Descriptive statistics. Not a model score. |
| `artifact_manifest.json` | SHA-256 of the files above. |

`features_*.csv` includes the join keys so a later report can attach audit fields outside the model matrix. Training code should select the feature columns only.

## Fit scope recorded with the transformer

The fit scope names the corpus `sent_messages_before_validation_window`, records the document count, the vocabulary size, the first and last sent time in the window, and states that warmup is included and validation and test are excluded. Checksums in `fit_metadata.json` tie the artifact to the published `med-synth-v2` files.
