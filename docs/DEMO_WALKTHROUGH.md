# Demo walkthrough

A short spoken demonstration of the simulated draft-review screen, in six steps that take about five to seven minutes in all: a safe email, a mistaken recipient, the explanation, the threshold tradeoff, a monitoring issue, and a rollback. Each step gives what to click or run, what the screen or command shows, the one point to make, and the honest limit.

Every figure in the "What it shows" blocks is generated from the stored records by `python -m med_docs report`. The records come from earlier runs, so no one-shot command is rerun to produce this page. Screen text and tables come from the generated [walkthrough](phase_7/WALKTHROUGH.md), the [drift replay](phase_8/DRIFT_REPLAY.md), and the [rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md); this script links to them instead of copying them.

All people, addresses, and messages are fictional. Scores are risk scores, not probabilities. Every decision is simulated: nothing is sent or stopped, and blocking is disabled.

## Before you start

Start the API and the screen as in the [usage guide](USAGE_GUIDE.md#start-the-demo), either as two processes or as two containers, and open the screen. Keep three pages open for steps 4 to 6: the [results](RESULTS.md), the drift replay, and the rollback rehearsal. The curated examples are in the sidebar; the screen's [guide](phase_7/UI_GUIDE.md) explains each part.

## Step 1: a safe email

**Do.** In the sidebar choose **Routine project update** and press **Assess draft**.

**What it shows.**

<!-- med-docs:begin demo_step_1 -->
- Recorded fixture `routine_allow` (validation draft `d003390`, scenario S05): decision **allow**, email risk score 8.216e-12 against `T_warn` 0.9996767, 4 recipients, 0 flagged.
- Screen: [step 1 of the generated walkthrough](phase_7/WALKTHROUGH.md#step-1-routine-project-update-s05-d003390) and its [screenshot](phase_7/screenshots/step1_routine_allow.png).
<!-- med-docs:end demo_step_1 -->

**The point.** An ordinary email passes without an interruption. The panel beside the message says "No warning from this policy." and adds that this is not a check that every recipient is correct.

**The limit.** Allow is not a guarantee, and one email is an anecdote. The denominators, intervals, and the mistakes the policy misses are in [results](RESULTS.md).

## Step 2: a mistaken recipient

**Do.** Choose **Forecast with an added vendor** and press **Assess draft**. Then remove the flagged recipient and assess again.

**What it shows.**

<!-- med-docs:begin demo_step_2 -->
- Recorded fixture `added_recipient_warn` (validation draft `d003027`, scenario S02): decision **warn**, email risk score 0.9997260, +4.93e-05 from `T_warn`; 1 of 2 recipients flagged (the one added as cc); codes `EXTERNAL_RECIPIENT`, `UNUSUAL_RECIPIENT_COMBINATION`, `CONTENT_RELATIONSHIP_MISMATCH`.
- Screen: [step 2a of the generated walkthrough](phase_7/WALKTHROUGH.md#step-2a-forecast-with-an-added-vendor-s02-d003027) and its [screenshot](phase_7/screenshots/step2_added_recipient_warn.png); the edit-and-reassess result is in [step 2b](phase_7/WALKTHROUGH.md#step-2b-the-same-draft-with-the-flagged-recipients-removed).
<!-- med-docs:end demo_step_2 -->

**The point.** The warning names the recipient and the field it is in, and keeps the others visible. After an edit the earlier result is hidden as stale, and the edited draft is assessed as a new request. Removing one flagged recipient does not guarantee an allow.

**The limit.** A warning asks the sender to check an address and is not proof of a mistake. This scenario is one the policy only partly catches: [results](RESULTS.md#2-outcomes-by-scenario) shows how many of its mistakes were warned.

## Step 3: the explanation

**Do.** Open **Assessment details** under the result and look at the flagged recipient's card.

**What it shows.** The codes the API returned for the flagged recipient, as the screen shows them:

<!-- med-docs:begin demo_step_3 -->
| Code the API returned | Kind | Text the API returned |
| --- | --- | --- |
| `EXTERNAL_RECIPIENT` | context | The address is outside the fictional organization; context, not proof of a mistake. |
| `UNUSUAL_RECIPIENT_COMBINATION` | context | These addressees have little support as a group in the available prior communication. |
| `CONTENT_RELATIONSHIP_MISMATCH` | reason | This draft differs from prior topics exchanged with this recipient. |
<!-- med-docs:end demo_step_3 -->

**The point.** There is one reason tied to the model and the rest is context. The reason is given only when raising that one input to its typical value would drop the recipient's score below the cutoff. The context codes say what is unusual about the address and are not proof of a mistake. The screen adds no reasons of its own and shows the API's text.

**The limit.** Codes are read from the feature row and from one rescoring of the frozen model. They are not causal, and they say nothing about the sender's intent. Evidence limitations such as little history are shown as limitations, not as warnings.

## Step 4: the threshold tradeoff, and a known miss

**Do.** Choose **Staffing note to a similar name** and assess it: the screen says there is no warning, and **About this example** labels it a known limitation. Then expand the collapsed threshold exploration and move the what-if cutoff down.

**What it shows.**

<!-- med-docs:begin demo_step_4 -->
- Cutoff `T_warn = 0.9996767050340489`, chosen on `validation_product_like`: 8 of 20 mistakes warned and 0 of 3,980 legitimate emails warned. The highest legitimate validation email scores 0.9973707, 2.31e-03 below the cutoff.
- Recorded fixture `legitimate_first_contact_allow` (draft `d003216`): allowed at 0.9973707 with an evidence limitation. This is the legitimate email that holds the cutoff up.
- Recorded known miss `known_miss_lookalike` (draft `d003002`, scenario S01, a mistake): allowed at 0.9818357, below the legitimate first contact. A cutoff low enough to warn on it would also warn on that legitimate email in the validation data.
- Screen: the collapsed threshold-exploration section, [step 5 of the generated walkthrough](phase_7/WALKTHROUGH.md#desired-and-measured-outcomes) (what-if counts on validation scores only; the decision above it never changes), and [step 4a](phase_7/WALKTHROUGH.md#step-4a-staffing-note-to-a-similar-name-s01-d003002) for the miss.
<!-- med-docs:end demo_step_4 -->

**The point.** The cutoff is where it is because of legitimate first contacts: they score just below it, so any cutoff low enough to warn on this lookalike mistake also warns on legitimate mail. The policy was chosen to interrupt no legitimate email on validation and accepts a low recall for that. The interruption budget, not the ranking score, decides how many senders are warned.

**The limit.** The miss is real: lookalike replacements, familiar-recipient topic mistakes, and mistaken first contacts were allowed on every subset. The what-if counts come from the subset that chose the cutoff, so they are a simulation and not evidence, and they never change the decision above them. A different cutoff would be a new policy with a new frozen test set. The zero false warnings on the test pass do not establish the budget, because emails are not shown to be independent ([AC01](RESULTS.md#5-acceptance-criteria) is insufficient evidence).

## Step 5: a monitoring issue

**Do.** Open the [drift replay](phase_8/DRIFT_REPLAY.md) and read the timeline and the three findings. To regenerate the documents from the stored records into a scratch folder, run `python -m med_monitor report --docs <scratch>/phase_8`.

**What it shows.**

<!-- med-docs:begin demo_step_5 -->
- Replay of 8 windows of 500 validation emails through the API (plan checksum `a16f64569efd3729…`); windows 1 to 4 are the reference period (2,000 emails). Windows 6 to 8 replace a growing share of routine mail with legitimate first contacts (injected share 4%, 8%, 16%).
- Last window: 80 of 500 emails injected, 80 with limited relationship history (reference: 25 of 2,000), 8 scoring just below the cutoff (reference: 2 of 2,000), 0 warned (reference: 6 of 2,000); highest allowed score 0.9985272, margin to the cutoff 1.15e-03 (reference 2.31e-03).
- Unable to assess in the replay: 0 of 4,000 requests. Reviewed labels on this traffic: 0; the review is simulated.
- Command output: [the drift replay timeline and its three findings](phase_8/DRIFT_REPLAY.md#timeline) (input drift, decision-rate change, and confirmed performance change are kept apart).
<!-- med-docs:end demo_step_5 -->

**The point.** Monitoring keeps three questions apart. Did the inputs move? Did the decision rate move? Did confirmed performance move? Here the inputs and the near-cutoff scores move toward first contacts while warnings stay rare, and confirmed performance cannot be stated because too few reviewed mistakes exist on either side. The proposed response is a shadow experiment on the affected senders and a written decision rule, not a change to the cutoff.

**The limit.** This is a simulation. The shift schedule was set so that the last window crosses the alert rules, so it shows the path from an alert to an investigation and does not measure how sensitive the monitor is. No real reviewer or production traffic exists, and the review is simulated.

## Step 6: rollback

**Do.** Open the [rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md). To rehearse again into a scratch record, run `python -m med_deploy rehearse --mode container --record <scratch>/rehearsal_container.json`.

**What it shows.**

<!-- med-docs:begin demo_step_6 -->
- Container rehearsal (2026-10-01T00:42:10Z): **passed**, 7 of 7 steps. Known-good image `85d67e46cbf7…` swapped for two failing candidates, each restored and re-verified (20 of 20 fixtures, `/ready` 200); image unchanged: yes.
  - `tampered_model` (one byte of model.joblib is flipped; policy.json records the model's SHA-256): `/ready` 503 (Checksum mismatch for model.joblib); `POST /assess` `unable_to_assess`, decision and score absent; the suite flagged 15 of 15 assessed fixtures; assessment disabled on the review screen: yes.
  - `missing_policy` (policy.json is absent): `/ready` 503 (Policy file /app/artifacts/med-policy-v2/policy.json does not exist); `POST /assess` `unable_to_assess`, decision and score absent; the suite flagged 15 of 15 assessed fixtures; assessment disabled on the review screen: yes.
- Process rehearsal: passed, 7 of 7 steps, published bundle files unchanged: yes.
- Bundle checks from monitoring: 9 of 9 altered bundles refused, each with no decision and no score.
- Command output: [rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md).
<!-- med-docs:end demo_step_6 -->

**The point.** A broken bundle fails closed: the service stays up, `/ready` says why, and `/assess` returns `unable_to_assess` with no decision and no score, so it can never produce an allow. The unit of change is a frozen, versioned bundle, and a rollback restores the known-good image and re-verifies it against the recorded fixtures.

**The limit.** This is a local rehearsal of an image swap with injected faults. It is not a live hot swap, a canary, or a shadow mode, none of which exists, and it does not show that a different healthy model can be promoted. Promotion needs the gates in the [runbook](phase_8/RUNBOOK.md#promotion-gates).

## Closing

The demo shows an end-to-end applied machine-learning system on fictional data: a warning policy with an explicit interruption budget, an evaluation kept honest by a frozen test set, a service that fails closed, monitoring that separates what moved from what is confirmed, and a rehearsed rollback. It also shows its limits: three kinds of mistake are missed, the budget claim is not confidence-supported, the data is synthetic, and nothing here shows that detection improved or that it would work on real mail. See [limitations and future work](LIMITATIONS_AND_FUTURE_WORK.md).

## Where the numbers come from

[Results](RESULTS.md) · [model card](MODEL_CARD.md) · [architecture](ARCHITECTURE.md) · [documentation index](README.md)
