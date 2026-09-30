"""Simulated draft-review screen. Start with `python -m med_ui` or `streamlit run src/med_ui/app.py`.

A client of the scoring API. The decision, scores, flagged recipients, codes,
and explanation sentences shown here are the API's; the presentation module
turns them into display text. Nothing here scores or applies a cutoff.
"""

from __future__ import annotations

import streamlit as st

from med_ui import client as api_client
from med_ui import examples as ex
from med_ui import exploration as xp
from med_ui import presentation as pres
from med_ui.config import FEEDBACK_LABELS, ROLES, UiSettings

ROLE_LABELS = {"to": "To", "cc": "Cc", "bcc": "Bcc"}


@st.cache_resource(show_spinner="Loading the fictional directory and curated examples")
def _catalog(data_dir: str, policy_dir: str) -> ex.Catalog:
    return ex.load_catalog(data_dir, policy_dir)


@st.cache_resource(show_spinner=False)
def _exploration(policy_dir: str) -> xp.ExplorationData:
    return xp.load_exploration(policy_dir)


# ------------------------------------------------------------------ state


def _set_form(form: pres.DraftForm) -> None:
    state = st.session_state
    state["f_timestamp"] = form.draft_timestamp
    state["f_sender"] = form.sender
    for role in ROLES:
        state[f"f_{role}"] = list(getattr(form, role))
    state["f_subject"] = form.subject
    state["f_body"] = form.body


def _current_form() -> pres.DraftForm:
    state = st.session_state
    return pres.DraftForm(
        draft_timestamp=state["f_timestamp"],
        sender=state["f_sender"] or "",
        to=tuple(state["f_to"]),
        cc=tuple(state["f_cc"]),
        bcc=tuple(state["f_bcc"]),
        subject=state["f_subject"],
        body=state["f_body"],
    )


def _load_example(catalog: ex.Catalog, key: str, names: dict[str, str]) -> None:
    example = catalog.examples[key]
    _set_form(example.form)
    st.session_state["loaded_example"] = key
    st.session_state["loaded_fingerprint"] = pres.fingerprint(pres.build_request(example.form, names))
    st.session_state["record"] = None
    st.session_state["feedback"] = {}


def _load_selected(catalog: ex.Catalog, names: dict[str, str]) -> None:
    _load_example(catalog, st.session_state["example_choice"], names)


def _assess(client: api_client.ApiClient, names: dict[str, str]) -> None:
    request = pres.build_request(_current_form(), names)
    response = client.assess(request)
    st.session_state["record"] = pres.AssessmentRecord(fingerprint=pres.fingerprint(request), response=response)
    st.session_state["feedback"] = {}


def _feedback(client: api_client.ApiClient, request_id: str, address: str, label: str) -> None:
    response = client.feedback(request_id, address, label)
    st.session_state["feedback"][(request_id, address)] = f"{label}: {pres.feedback_note(response)}"


# ----------------------------------------------------------------- screen


def main() -> None:
    st.set_page_config(page_title="Draft review (simulation)", layout="wide")
    settings = UiSettings.from_env()
    catalog = _catalog(str(settings.data_dir), str(settings.policy_dir))
    exploration = _exploration(str(settings.policy_dir))
    names = ex.display_names(catalog.contacts)
    expected = xp.expected_bundle(exploration)
    client = api_client.make_client(settings)
    readiness = pres.readiness_view(client.ready(), expected)
    state = st.session_state

    if "record" not in state:
        state["record"] = None
        state["feedback"] = {}
        state["loaded_example"] = None
        first = next(iter(catalog.examples))
        state["example_choice"] = first
        _load_example(catalog, first, names)
        params = st.query_params
        if params.get("example") in catalog.examples:
            state["example_choice"] = params["example"]
            _load_example(catalog, params["example"], names)
            if params.get("assess") == "1" and readiness.ok:
                _assess(client, names)

    if not readiness.ok:
        _readiness_problem(readiness)
    _sidebar(catalog, names)

    st.markdown("## Draft review")
    st.caption(pres.SIMULATION_NOTE + " " + pres.RISK_NOTE)
    message_column, review_column = st.columns([3, 2], gap="large")
    with message_column:
        _compose(catalog, names, pres.parse_timestamp(state["f_timestamp"]))
    with review_column:
        # Computed after the compose widgets, so any edit hides the earlier result.
        view = pres.result_view(state["record"], pres.fingerprint(pres.build_request(_current_form(), names)), expected)
        with st.container(border=True, key="review_panel"):
            st.markdown("#### Review before sending")
            st.button(
                "Assess draft",
                key="assess",
                type="primary",
                width="stretch",
                disabled=not readiness.ok,
                on_click=_assess,
                args=(client, names),
                help=None if readiness.ok else "The scoring service is not ready.",
            )
            _action(pres.action_message(view))

    st.divider()
    st.header("Assessment details")
    _result(view, client)

    with st.expander(xp.exploration_title(exploration), expanded=False):
        _exploration_section(exploration, view)
    with st.expander("Service status and versions", expanded=False):
        _readiness_details(readiness)


def _readiness_problem(readiness: pres.ReadinessView) -> None:
    """At the top only when something is wrong, because it explains why assessment is disabled."""
    st.error(readiness.headline)
    if readiness.problem:
        st.caption(readiness.problem)


def _readiness_details(readiness: pres.ReadinessView) -> None:
    """The /ready check and the served versions, collapsed at the bottom when the service is ready."""
    if not readiness.ok:
        st.write("Not ready. See the message at the top of the page.")
        return
    st.write(readiness.headline)
    st.table({"Item": [label for label, _ in readiness.items], "Value": [value for _, value in readiness.items]})


def _sidebar(catalog: ex.Catalog, names: dict[str, str]) -> None:
    state = st.session_state
    with st.sidebar:
        st.header("Curated examples")
        st.caption("Fictional validation drafts chosen by rule. Loading one replaces the draft in the form.")
        keys = list(catalog.examples)
        st.selectbox("Example", keys, key="example_choice", format_func=lambda key: catalog.examples[key].rule.title)
        st.button("Load example", key="load_example", on_click=_load_selected, args=(catalog, names))
        for key, reason in catalog.unmatched.items():
            st.caption(f"Example {key} is not available: {reason}")

        st.header("Simulation settings")
        st.text_input(
            "Simulated send time",
            key="f_timestamp",
            help="ISO 8601 with a timezone, for example 2025-05-01T12:56:10Z. The service uses only mail sent before this time.",
        )
        if pres.parse_timestamp(state["f_timestamp"]) is None:
            st.caption("This time does not parse with a timezone, so the directory is not filtered. The service will reject it.")

        st.header("About this example")
        st.caption("The fictional story behind the loaded example. It is not part of the request, and the model never sees it.")
        key = state.get("loaded_example")
        if key is None:
            st.write("No example loaded.")
            return
        example = catalog.examples[key]
        story = example.story
        current = pres.fingerprint(pres.build_request(_current_form(), names))
        if current != state.get("loaded_fingerprint"):
            st.warning("The draft was edited after this example was loaded, so the story may no longer describe it.")
        st.markdown(f"**{story.scenario_id} · {story.scenario_name}**")
        st.write(story.summary)
        st.markdown("**Stipulated intent**")
        for person in story.recipients:
            verdict = "intended" if person.intended else "unintended"
            st.markdown(f"- `{person.address}`: {verdict}. {person.stipulation}")
        st.markdown("**Desired outcome (product intent)**")
        st.write(story.desired)
        st.markdown("**Recorded policy outcome for this scenario (validation)**")
        for line in story.recorded:
            st.markdown(f"- {line}")
        if example.rule.stored_decision == "allow" and example.rule.misdirected:
            st.error("Known limitation: the policy allows this kind of mistake. It is shown on purpose.")
        st.markdown("**Selection rule**")
        st.caption(f"{example.rule.rule} Draft {example.draft_id}, {example.subset}.")


def _compose(catalog: ex.Catalog, names: dict[str, str], moment) -> None:
    """The message as a sender sees it: From, To, Cc, Bcc, Subject, Body."""
    state = st.session_state
    senders = ex.internal_senders(catalog.contacts, moment)["email_address"].tolist()
    if state["f_sender"] and state["f_sender"] not in senders:
        senders = [state["f_sender"]] + senders
    st.selectbox("From", senders, key="f_sender", format_func=lambda address: ex.contact_label(address, names))
    visible = ex.visible_contacts(catalog.contacts, moment)["email_address"].tolist()
    for role in ROLES:
        selected = list(state[f"f_{role}"])
        options = selected + [item for item in visible if item not in selected]
        st.multiselect(
            ROLE_LABELS[role],
            options,
            key=f"f_{role}",
            format_func=lambda address: ex.contact_label(address, names),
            accept_new_options=True,
            # No "select all": one Enter must never add a whole filtered list of recipients.
            select_all=False,
            filter_mode="contains",
            placeholder="Choose a contact or type an address",
            help=f"{len(visible)} fictional contacts are in the directory at the send time. A typed address is sent as written.",
        )
    st.text_input("Subject", key="f_subject")
    st.text_area("Body", key="f_body", height=220)


def _action(message: pres.ActionMessage) -> None:
    """The next step, directly under the Assess button. Built from the API response only."""
    if message.kind == "empty":
        st.caption(message.headline)
        return
    callout = {"warn": st.warning, "allow": st.info, "unable": st.error, "stale": st.warning}[message.kind]
    with st.container(border=True, key="action_message"):
        callout(f"**{message.headline}**")
        if message.items_heading:
            st.markdown(f"**{message.items_heading}**")
        for item in message.items:
            name = f" ({item.display_name})" if item.display_name else ""
            lines = [f"- [`{item.address}`](#{item.anchor}){name}, in **{item.fields}**"]
            # Plain-language text from the service for the sender; code names stay in the details below.
            lines += [f"    - {line.kind.capitalize()}: {line.text}" for line in item.lines]
            if not item.lines and message.kind == "warn":
                lines.append(f"    - {pres.NO_CODE_TEXT}")
            st.markdown("\n".join(lines))
        for note in message.notes:
            st.caption(note)


def _result(view: pres.ResultView, client: api_client.ApiClient) -> None:
    if view.kind == "empty":
        st.info(view.headline)
        return
    if view.kind in ("stale", "unable"):
        st.caption("No decision, risk score, or recipient table for the current draft. See the message above.")
        return

    banner = st.warning if view.decision == "warn" else st.info
    banner(f"**{view.headline}**")
    left, middle, right = st.columns(3)
    left.metric("Email risk score", view.email_risk_text)
    middle.metric("T_warn (risk score cutoff)", pres.format_score(view.t_warn))
    right.metric("Email risk score minus T_warn", view.margin_text)
    if view.flagged:
        st.markdown("**Flagged recipients:** " + ", ".join(f"`{item}`" for item in view.flagged))
    st.dataframe(pres.recipient_table(view), hide_index=True)

    st.subheader("Recipients")
    feedback = st.session_state["feedback"]
    for index, row in enumerate(view.recipients):
        with st.container(border=True):
            flag = "flagged" if row.flagged else "not flagged"
            # The anchor lets the action message link straight to this card.
            st.subheader(f"`{row.address}`", anchor=pres.recipient_anchor(index))
            name = f"{row.display_name} · " if row.display_name else ""
            st.markdown(f"{name}{', '.join(row.roles)} · risk score {row.risk_text} · {flag}")
            for line in row.codes + row.limitations:
                st.markdown(f"- {line.kind.capitalize()} `{line.code}`: {line.text}")
            if view.request_id:
                buttons = st.columns(len(FEEDBACK_LABELS) + 2)
                for slot, label in zip(buttons, FEEDBACK_LABELS, strict=False):
                    slot.button(
                        f"Mark {label}",
                        key=f"fb_{index}_{label}",
                        on_click=_feedback,
                        args=(client, view.request_id, row.address, label),
                    )
                note = feedback.get((view.request_id, row.address))
                if note:
                    st.caption(note)

    st.subheader("Explanation from the service")
    for sentence in view.explanation:
        st.markdown(f"- {sentence}")
    for note in view.notes:
        st.caption(note)
    with st.expander("Provenance", expanded=False):
        st.table({"Item": [label for label, _ in view.provenance], "Value": [value for _, value in view.provenance]})
    st.caption(
        "Feedback is stored by the service for later review. It is not a label until reviewed, and it never "
        "changes the model, the policy, or this decision."
    )


def _exploration_section(data: xp.ExplorationData, view: pres.ResultView) -> None:
    for note in xp.exploration_notes(data):
        st.caption(note)
    options = xp.cutoff_options(data)
    cutoff = st.select_slider(
        "What-if cutoff on the email risk score",
        options=options,
        value=data.t_warn,
        key="explore_cutoff",
        format_func=lambda value: f"{value:.7f}" + (" (policy)" if value == data.t_warn else ""),
    )
    st.write(xp.counts_sentence(xp.counts_at(data, cutoff)))
    st.markdown("**What lower cutoffs would cost on validation**")
    rows = xp.tradeoff_rows(data)
    st.dataframe(
        [
            {
                "Cutoff": f"{row['cutoff']:.7f}" + (" (policy)" if row["is_policy"] else ""),
                "Mistakes warned": f"{row['warned_mistakes']} of {row['mistakes']}",
                "False warnings": f"{row['false_warnings']} of {row['legitimate']}",
            }
            for row in rows
        ],
        hide_index=True,
    )
    if view.kind == "assessed":
        st.write(xp.position_sentence(xp.position_of(data, view.email_risk_score)))
    else:
        st.caption("Assess a draft to see where its email risk score falls.")


main()
