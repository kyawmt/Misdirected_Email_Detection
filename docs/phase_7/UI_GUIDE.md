# Phase 7 — UI guide

The draft-review screen is a small Streamlit app in `src/med_ui/`. It is a client of the Phase 6 scoring API: it sends Phase 1 requests over HTTP (`GET /ready`, `POST /assess`, `POST /feedback`) and shows what the API returns. It does not score, apply a cutoff, read the model, or add reason codes. Every decision is simulated, and every number is a risk score, not a probability.

## Install and start

From the repository root, with Python 3.11 or newer:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ui]"
```

The `ui` extra adds Streamlit and httpx; the core install does not need them. Streamlit brings in pyarrow. When pyarrow is importable, pandas 3 stores strings in Arrow by default. That leaves every result unchanged, but it slows the data and feature commands: `python -m med_data validate` took 159.8 s with pyarrow against 49.1 s without it on the reference machine, with the same 31 checks passing. `tests/conftest.py` pins pandas to Python string storage, so `pytest` runs as before. To keep the pipeline commands fast, install the UI in its own virtual environment.

Start the API in one terminal:

```bash
python -m med_api serve
```

Start the UI in another terminal. It opens on `http://localhost:8501` and calls the API at `http://127.0.0.1:8000`:

```bash
python -m med_ui
```

`python -m med_ui serve --port 8501 --api http://127.0.0.1:8000` sets both explicitly, and `streamlit run src/med_ui/app.py` also works. Environment variables: `MED_UI_API_URL` (API base URL), `MED_UI_ROOT` (repository root, default the working directory), `MED_UI_DATA` and `MED_UI_POLICY_DIR` (the published dataset and policy directory). All UI settings, including the curated example rules, live in [config.py](../../src/med_ui/config.py). It reads versions and paths from `med_api.version` and `med_policy.version`.

`python -m med_ui walkthrough` regenerates the [walkthrough](WALKTHROUGH.md) from the running API.

## The screen

The page has two parts. The **sidebar** is for testing: curated examples, the simulated send time, and the story behind the loaded example. The **main area** is what a sender sees: the message on the left and, beside it, a **Review before sending** panel with the **Assess draft** button and the result in plain language. On a laptop-sized window both are visible without scrolling. Details for reviewers (scores, recipient cards, feedback, exploration, service status) are below.

### Readiness check

On every page load the UI calls `GET /ready`. The service must report exactly the contract and snapshot this screen speaks, and the model, feature, and policy versions and the exact `T_warn` of the local policy file that the exploration view reads. If the service does not answer, is not ready, reports anything else, or does not report blocking as disabled, a red banner at the top of the page says so and the **Assess draft** button is disabled.

When the service is ready, nothing appears above the message. The status, the served versions, `T_warn`, and "Blocking: disabled" are in the collapsed **Service status and versions** section at the bottom of the page. Each assessment's own versions are in its **Provenance** panel.

### Message

From, To, Cc, Bcc, Subject, and Body, as in a mail client. The From list holds internal `demo.example` contacts. Each of To, Cc, and Bcc is one box: pick a contact from the directory (every fictional contact visible at the send time, from the published `med-synth-v4` contacts table) or type an address and choose "Add: …". A typed address is sent as written; the API normalizes and validates it, so an unknown or malformed address is shown as unable to assess. The boxes have no "select all", so one Enter never adds a whole filtered list. The form shows no labels, scenarios, splits, or families. The request carries only the Phase 1 fields; it has no draft reference.

The **Simulated send time** (ISO 8601 with a timezone) is in the sidebar under **Simulation settings**. It is part of the request: the service uses only mail sent before it, and the directory lists only contacts visible at it.

### Curated examples and "About this example"

The sidebar loads a curated example into the form. Examples are validation drafts chosen by rule from the policy's stored validation decisions, never by draft id, and never from the frozen test subsets. Validation ids come from the split manifest first; the drafts, recipients, and labels tables are then streamed one record at a time and only validation records are kept, so no frozen test record (including the dataset's walkthrough drafts) enters memory as a table:

| Example | Rule |
| --- | --- |
| Routine project update | S05 internal project draft at the median email risk score among those allowed on `validation_product_like`. |
| Forecast with an added vendor | S02 added-recipient mistake warned on `validation_product_like`: fewest recipients, then highest email risk score. |
| Introduction to a new collaborator | Legitimate first contact (S03 or S06) allowed on `validation_product_like` with the highest email risk score. |
| Staffing note to a similar name | S01 lookalike mistake allowed on `validation_product_like` with the highest email risk score (known miss). |
| Compensation note to a familiar contact | S04 familiar-recipient topic mistake allowed on `validation_product_like` with the highest email risk score (known miss). |
| Status update to an autocompleted contact | S11 mistaken first contact allowed on `validation_product_like` with the highest email risk score (known miss). |
| Kickoff invitation to a familiar contact | S07 legitimate topic change allowed on `validation_product_like` with the highest email risk score. |
| First mail from a new sender | S09 cold-start draft at the median email risk score among those allowed on `validation_product_like`. |

"About this example" shows the fictional story: the scenario, the stipulated intent for each recipient, the desired outcome from the [scenario list](../phase_1/SCENARIOS.md), the recorded validation outcome for the scenario, and the selection rule. The panel says that the story is not part of the request and that the model never sees it. Known misses carry a "known limitation" note. If the draft is edited after loading, the panel says the story may no longer describe it.

`?example=<key>&assess=1` in the URL loads an example and assesses it on first load (keys: `routine`, `added_recipient`, `first_contact`, `lookalike_miss`, `topic_miss`, `first_contact_miss`, `topic_change`, `cold_start`). The screenshots use this.

### Action message

In the **Review before sending** panel, directly under **Assess draft**, the screen answers "should I pause, and where do I look?" It is built only from the API response, never from the curated example's story, scenario, or labels. It names no score, ranks nothing by score, and adds no reason.

| State | Message | What follows |
| --- | --- | --- |
| Warn | "Pause and review before sending." | "Check these recipients and the field they are in:", then every flagged recipient in the API's order. Each shows its address (a link that jumps to its recipient card), its name, the field it is in (To, Cc, or Bcc, from the API's roles), and the API's plain-language text for each code, labeled reason or context. The code names themselves (for example `EXTERNAL_RECIPIENT`) are shown in the recipient cards under **Assessment details**. "A warning asks you to check these addresses. It is not proof of a mistake." |
| Allow | "No warning from this policy." | "This is not a check that every recipient is correct, and the policy misses some kinds of mistakes. Review the recipients yourself before sending." When the API returned evidence limitations: "Less evidence for:", those recipients with their field and the API's limitation text (code names are in the recipient cards), and "Less evidence is an evidence limitation from the service, not a warning." |
| Unable to assess | "Assessment unavailable. Check recipients manually before sending." | The category (`invalid_input`, `unavailable`, or `unexpected_response` for a response the screen does not accept), the plain-language category text, the directory sentence for an address outside the snapshot, and the service message. No decision and no risk score. An unreachable service is shown the same way. |
| Stale | "The draft changed after the last assessment. Assess the edited draft again; the earlier result no longer applies." | Nothing from the earlier result. |
| Not assessed | "Not assessed yet. Assess the draft to see whether the service asks you to pause." | Nothing. |

The known-limitation notice for curated mistakes the policy misses stays in the "About this example" panel, because it comes from the example's story, not from the API.

### Assessment details

- **Assessed:** "Simulated decision: allow" or "Simulated decision: warn" (the API's decision), the email risk score, `T_warn`, and their difference. Then one table row and one card per unique recipient: address, name, roles, risk score, flagged or not, the API's codes with the API's text, and evidence limitations. `CONTENT_RELATIONSHIP_MISMATCH` is labeled a reason; `EXTERNAL_RECIPIENT`, `LOOKALIKE_CONTACT_CONTEXT`, and `UNUSUAL_RECIPIENT_COMBINATION` are labeled context; `LIMITED_RELATIONSHIP_HISTORY` and `LIMITED_TEXT` are evidence limitations. Codes appear only where the API sent them, and an unknown code is shown as sent. Below the cards come the API's explanation sentences and, in a collapsed panel, the provenance.
- **Unexpected response:** an assessed response is displayed only if it is complete and consistent: simulation mode, blocking reported disabled, a finite `T_warn`, risk scores from 0 to 1, valid roles, well-formed codes, a flagged list that matches the flagged recipients, `warn` only with flagged recipients, and the same versions and cutoff that readiness checked. Anything else is shown as unable to assess with no decision, no risk score, and no recipient table.
- **Unable to assess:** the action message carries the category and the service message. The result section shows no decision, no risk score, and no recipient table. A well-formed address that is not in the directory snapshot shows "This address is not in the directory snapshot, so the draft could not be assessed."
- **Stale:** any change to any field or recipient hides the previous result and its action message. Nothing from the old result is shown until the edited draft is assessed as a new request. Removing a flagged recipient and reassessing may still warn.
- **Recipient cards:** each card's heading is the address, shown as text (not a mail link), with an anchor the action message links to.

### Feedback

Each recipient card has **Mark intended** and **Mark unintended**. One click sends one `POST /feedback`. The screen says the feedback is stored for later review, is not a label until reviewed, and does not change the model, the policy, or the decision. Nothing is retrained or resubmitted.

### Threshold exploration (collapsed)

"Threshold exploration on validation data (validation_product_like), what-if only". It reads only the stored `validation_scores.csv` (round-trip float parsing) and the cutoff in `policy.json`. A slider moves a what-if cutoff over stored validation scores, with the default policy cutoff marked. The section shows how many validation mistakes and how many legitimate validation emails would be warned at that cutoff, a table of lower cutoffs and what they would cost, and where the current draft's email risk score falls. It never changes the decision above, never calls a different policy, and never reads test results. These counts come from the subset that chose the cutoff, so they are not independent evidence.

## Screenshots

Captured with headless Chrome over the DevTools protocol from the running app, using the `?example=...&assess=1` links. All data is fictional.

Step 1, routine mail: "No warning from this policy."

![Routine example, simulated allow](screenshots/step1_routine_allow.png)

Step 2, an added external recipient: "Pause and review before sending.", with the recipient, its field (Cc), and the API's codes:

![Added-recipient example, simulated warn](screenshots/step2_added_recipient_warn.png)

Step 4, a lookalike mistake the policy allows. The action message shows no warning, and the "About this example" panel labels it a known limitation:

![Lookalike example, simulated allow, known limitation](screenshots/step4_known_miss_lookalike.png)

## What the UI does not change

The UI makes these limits visible; it does not remove them:

- Lookalike replacements (S01), familiar-recipient topic mistakes (S04), and mistaken first contacts (S11) are allowed by the served policy on every validation and test subset. See the [walkthrough](WALKTHROUGH.md#limitations-the-walkthrough-makes-visible).
- A well-formed address outside the directory snapshot is unable to assess (`unavailable`), not a warning.
- Scores are uncalibrated risk scores. Blocking is disabled.
- The warning budget (AC01) is recorded as insufficient evidence.
- The measured API latency (AC05) covers the API boundary only; UI rendering time is not part of it.
