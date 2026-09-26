# Phase 1 — Input/output specification

Status: conceptual product contract, version 0.1. No endpoint, executable schema, model, data table, or UI is implemented here. Transport details belong to Phase 6. Assumptions A1–A6 are defined in the [product brief](PRODUCT_BRIEF.md).

## Assessment input

| Field | Requirement | Meaning and constraint |
| --- | --- | --- |
| Draft timestamp | Required | Unambiguous timestamp with timezone, interpreted as the assessment's historical cutoff. |
| Sender | Required | One fictional email address and optional display name. Sender must belong to the configured fictional organization. |
| To, Cc, Bcc | Required lists; individual lists may be empty | Address entries with optional display names. At least one unique recipient across all lists; at most 20. Each unique address receives one result, preserving its roles. |
| Subject | Required text; may be empty | Plain text, at most 500 characters. |
| Body | Required text; may be empty | Plain text, at most 20,000 characters. No attachments or HTML parsing. |
| Historical context reference | Required | Identifier of a server-resolved fictional context snapshot, providing contact identities and earlier communication where available. An empty snapshot is valid; an unknown reference is not. |
| Draft reference | Optional | Caller-supplied correlation label; not a feature or proof that content is unchanged. Every assessment receives a new request identifier. |

**Assumption A7 — Simplified input handling:** The demo accepts fictional ASCII addresses; matching is case-insensitive across the whole address within these fixtures. Trim surrounding whitespace, merge repeated addresses across roles, preserve original display text, and reject malformed entries. This deliberately limited convention is not a claim about universal email address equivalence. Distribution lists, aliases that require directory expansion, and internationalized address handling are outside scope. Text limits count characters, not model tokens. Over-limit requests are rejected explicitly, not silently truncated.

**Assumption A8 — Context boundary:** The caller chooses a fictional snapshot reference rather than uploading arbitrary mail history on each assessment. The scorer must resolve only history with event times strictly earlier than the draft timestamp; exclude the draft itself and future events. If that temporal view cannot be established, the request is unassessable. Snapshot/version and effective cutoff must be reported. This is an availability contract; storage, historical data schemas, and feature definitions are deferred.

The scoring input must not include scenario IDs, intended-recipient answers, labels, corruption metadata, or future corrections. Fictional examples shown to an interviewer may have a separate narrative with those answers; the scorer cannot use it. Organization/domain configuration is versioned context, not inferred from an untrusted label in the draft.

## Successful assessment output

| Field | Meaning |
| --- | --- |
| Request identifier and contract version | Unique assessment identifier and input/output contract version. |
| Assessment status | `assessed` only when every unique recipient has a valid score and a valid decision policy is available. |
| Recipient results | One entry per unique addressed recipient, with address, roles, risk score, flagged status, reason codes, and evidence limitations. |
| Email risk score | Maximum of the recipient risk scores, using comparable scores from the same model bundle. |
| Decision | `allow`, `warn`, or `block`; all are simulated actions. |
| Flagged recipients | References to all recipients whose scores meet or exceed the active warning threshold, not just the maximum-scoring address. |
| Explanation | Concise descriptions of contributing evidence and any limited-history/text context. No assertion of certainty about sender intent. |
| Provenance | Model bundle version, feature specification version, context snapshot/version, effective historical cutoff, and threshold-policy version. The policy identifies its threshold values and whether blocking is enabled. |
| Timing and mode | Assessment duration and explicit simulation indicator. Any future exploratory threshold policy must be visibly distinct from the default policy. |

Risk is a finite number from 0 to 1 with higher values indicating more suspicion. Until calibration is validated, present it as a **risk score**, never “probability of a wrong recipient.” Explainability is limited to supported signals; no invented evidence or unimplemented group-topic explanation is allowed.

## Decision semantics

Let the warning threshold be **T_warn**. If blocking is enabled, a separately justified **T_block** must exceed T_warn. Neither numeric value is selected in Phase 1. These are model/policy configuration choices for Phase 5.

| Condition on an assessed draft | Decision and user meaning |
| --- | --- |
| Email risk below T_warn | **Allow:** no intervention under this policy; no guarantee that every recipient is correct. |
| Email risk at or above T_warn, with blocking disabled | **Warn:** ask the sender to review the flagged recipient(s). |
| Blocking enabled and email risk at or above T_warn but below T_block | **Warn:** review requested. |
| Blocking enabled and email risk at or above T_block | **Simulated block:** display that this policy would stop sending pending correction/review; no actual email action occurs. |

Equality belongs to the higher-intervention band. A low-ranked recipient is not automatically flagged. An all-intended email may have zero flagged recipients; a misdirected email may contain more than one unintended recipient. Maximum aggregation is a project extension and requires recipient-count error analysis before being trusted.

Blocking is disabled by default. It can be enabled only after separate evaluation justifies its stricter operating point and documented false-block tolerance. Until then, even a high score yields at most warn. Missing or invalid threshold configuration causes unable to assess rather than a guessed threshold.

## Explanation vocabulary

These names define candidate product-facing concepts, not a completed feature catalog. Return a concept only if an implemented signal supports it and it contributed to the assessment; exact attribution logic is later work.

| Candidate reason/context code | Intended plain-language meaning |
| --- | --- |
| CONTENT_RELATIONSHIP_MISMATCH | This draft differs from prior topics exchanged with this recipient. |
| UNUSUAL_RECIPIENT_COMBINATION | These addressees have little support as a group in the available prior communication. |
| LOOKALIKE_CONTACT_CONTEXT | A similar contact identity and other context warrant review; similarity alone is not a mistake finding. |
| LIMITED_RELATIONSHIP_HISTORY | Little or no prior communication is available; an evidence limitation, not a verdict. |
| EXTERNAL_RECIPIENT | The address is outside the fictional organization; context, not proof of a mistake. |
| LIMITED_TEXT | Little text is available for content assessment; an evidence limitation. |

## Non-assessed outcomes

**Assumption A9 — Whole-request failure:** Do not issue a partial email decision if any recipient cannot be assessed. Return `invalid_input` for malformed/unsupported inputs or `unavailable` for missing context, missing artifacts, timeouts, or scoring failures. In either case, the user-facing outcome is **unable to assess**; decision and risk scores are absent/null, and flagged recipients are not represented as a successful empty result. Include a request identifier, a concise error category/message, and versions only where actually known.

No history is different from a broken context lookup. A valid empty-history case may be assessed using a later validated fallback with explicit limitations; if no such fallback exists, return unavailable. Do not force an all-new sender into either allow or warn by definition.

Edits require a fresh assessment; results apply only to the draft content and recipients that produced them. The interface must not retain an old allow decision as if it applied to an edited draft. User feedback, when added in later phases, is separate from scoring input and never silently changes the deployed model.

## Research boundary

Per-recipient assessment and composition-time feedback follow R1/R4. Numeric scale, maximum aggregation, fields, limits, errors, and version metadata are our product/engineering extensions. Full references and limitations are in the [Research Basis](../../PROJECT_PLAN.md#research-basis). Endpoint routing, persistence, preprocessing algorithms, and API implementation are intentionally left to later phases.

