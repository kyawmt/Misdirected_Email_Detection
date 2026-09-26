# Phase 1 — Scenario list

These are product narratives, not generated records, a training dataset, or an executed test suite. Intendedness is stipulated for each fictional story. Described historical patterns are requirements for later fixtures, not claims that data already exists. All addresses are fictional and comply with assumption A1 in the [product brief](PRODUCT_BRIEF.md).

The first five scenarios form the core walkthrough. Desired outcomes express product intent; a future model may miss them. Do not hard-code scenario IDs, stated intentions, or expected decisions into scoring. No scenario requires a block while blocking is disabled.

## Core walkthrough

| ID | Draft and preceding context | Stipulated intent | Desired behavior and rationale |
| --- | --- | --- | --- |
| S01 — Lookalike replacement | Maya sends an internal staffing update to `alex.chen@demo.example`, having selected that contact instead of `alex.chan@demo.example`. Prior staffing exchanges involve Alex Chan; exchanges with Alex Chen concern office equipment. | Alex Chen is unintended; Alex Chan was intended. This is a replacement mistake. | Warn on Alex Chen when combined context supports the risk. Explain the mismatch without claiming to know the correct replacement. Name resemblance alone is insufficient. |
| S02 — Added external recipient | Maya addresses a project budget draft to the usual internal project group plus `lee@vendor.example`, a fictional supplier normally involved only in purchase scheduling. | The internal recipients are intended; Lee was accidentally added. | Warn on Lee using multiple contextual signals. Keep the other recipients visible; do not characterize all external communication as risky. |
| S03 — New legitimate collaborator | Maya sends a project introduction to `jordan@demo.example`, a newly assigned collaborator with no direct prior exchanges with Maya. The text introduces Jordan to the project. | Jordan is intended. | Aim to allow; show limited relationship history as context rather than a mistake label. A warning counts as a false positive. Optional group-topic evidence must not become a prerequisite for the core demo. |
| S04 — Familiar recipient, unusual topic | Maya sends an internal compensation-planning draft to `sam@demo.example`, a frequent facilities contact, instead of an intended HR contact. The preceding relationship is strong but concerns different work. | Sam is unintended. | Warn if content mismatch and other evidence justify it. Demonstrate why familiarity alone is insufficient; compare with S07 before assuming every topic change is risky. |
| S05 — Routine legitimate mail | Two variants: a weekly project update to the established internal group; a purchase-scheduling update to `lee@vendor.example` with consistent prior exchanges. | Every recipient is intended in both variants. | Allow both. These establish the ordinary internal and external paths and must remain in evaluation even when there is no suspicious recipient. |

## Boundary and reliability scenarios

| ID | Situation and intent | Required interpretation |
| --- | --- | --- |
| S06 — Uncommon external domain, valid purpose | A planned first contact to `rina@newpartner.example` introduces a collaboration. Rina is intended despite sparse history and a new domain. | Aim to allow. Count any intervention as a false positive; novelty does not supply the ground-truth label. |
| S07 — Legitimate topic change | Maya invites familiar facilities contact Sam to a new project kickoff unrelated to their previous messages. Sam is intended. | Aim to allow. This is a counterexample to S04; unusual content alone is not definitive. |
| S08 — Multiple recipients and roles | Compare an all-intended group message with a variant that adds an unintended contact in Cc or Bcc. Include a variant with two unintended recipients. | Assess every unique addressee across roles. One email intervention counts once; recipient results identify each flagged address. Do not force exactly one recipient to be wrong. Flagging only a legitimate recipient in the misdirected variant is an attribution error. |
| S09 — Cold start or little text | A new fictional sender has no earlier messages, or a draft has an empty subject/body. Intendedness depends on the story, not on missing evidence. | Treat empty history/text as a valid boundary case. Use the later validated fallback with a visible limitation, or return unable to assess if unsupported. Never manufacture high confidence or silently equate missing history with low risk. |
| S10 — Invalid or unavailable assessment | A draft has no recipients, a malformed address, an inaccessible snapshot, or a scoring dependency failure. | Return a non-assessed outcome without a risk score or allow decision. Clearly separate invalid input from unavailable service/context. |

## Narrative walkthrough and safeguards

1. Start with S05 to establish the no-intervention path.
2. Show S01 or S02, inspect the recipient and contributing signals, and correct the draft.
3. Reassess the edited draft as a new request. Removing one suspicious recipient does not guarantee allow if another remains risky.
4. Show S03 and contrast S04 with S07 to explain false-positive tradeoffs.
5. Explain that threshold exploration and all send/block outcomes are simulations, and that later user corrections require review before becoming labels.

## Research traceability and limits

R1 motivates message–recipient incompatibility and added-recipient mistakes; replacement variants are our adaptation. R2 motivates S03's legitimate first contact. R3 motivates communication-group consistency, and R4 motivates the pre-send review. S06–S10 are our product guardrails and boundary cases. These connections use the evidence already summarized in the [Research Basis](../../PROJECT_PLAN.md#research-basis); the narratives do not reproduce a paper benchmark.

Scenario frequency, exact histories, labels for generated variants, and dataset size are deferred to Phase 2. Numeric scores, threshold values, and achieved outcomes are deferred to modeling and evaluation. This document selects no implementation or data-generation method.

