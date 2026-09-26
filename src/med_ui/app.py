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

FORM_KEYS = ("f_timestamp", "f_sender", "f_to", "f_cc", "f_bcc", "f_to_other", "f_cc_other", "f_bcc_other", "f_subject", "f_body")


@st.cache_resource(show_spinner="Loading the fictional directory and curated examples")
def _catalog(data_dir: str, policy_dir: str) -> ex.Catalog:
    return ex.load_catalog(data_dir, policy_dir)


@st.cache_resource(show_spinner=False)
def _exploration(policy_dir: str) -> xp.ExplorationData:
    return xp.load_exploration(policy_dir)


# ------------------------------------------------------------------ state


def _set_form(form: pres.DraftForm, names: dict[str, str], known: set[str]) -> None:
    state = st.session_state
    state["f_timestamp"] = form.draft_timestamp
    state["f_sender"] = form.sender
    for role in ROLES:
        addresses = getattr(form, role)
        state[f"f_{role}"] = [item for item in addresses if item.casefold() in known]
        state[f"f_{role}_other"] = ", ".join(item for item in addresses if item.casefold() not in known)
    state["f_subject"] = form.subject
    state["f_body"] = form.body


def _current_form() -> pres.DraftForm:
    state = st.session_state
    return pres.DraftForm(
        draft_timestamp=state["f_timestamp"],
        sender=state["f_sender"] or "",
        to=tuple(state["f_to"]) + pres.split_addresses(state["f_to_other"]),
        cc=tuple(state["f_cc"]) + pres.split_addresses(state["f_cc_other"]),
        bcc=tuple(state["f_bcc"]) + pres.split_addresses(state["f_bcc_other"]),
        subject=state["f_subject"],
        body=state["f_body"],
    )


def _load_example(catalog: ex.Catalog, key: str, names: dict[str, str], known: set[str]) -> None:
    example = catalog.examples[key]
    _set_form(example.form, names, known)
    st.session_state["loaded_example"] = key
    st.session_state["loaded_fingerprint"] = pres.fingerprint(pres.build_request(example.form, names))
    st.session_state["record"] = None
    st.session_state["feedback"] = {}


def _load_selected(catalog: ex.Catalog, names: dict[str, str], known: set[str]) -> None:
    _load_example(catalog, st.session_state["example_choice"], names, known)


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
    known = set(names)
    client = api_client.make_client(settings)
    readiness = pres.readiness_view(client.ready())
    state = st.session_state

    if "record" not in state:
        state["record"] = None
        state["feedback"] = {}
        state["loaded_example"] = None
        first = next(iter(catalog.examples))
        state["example_choice"] = first
        _load_example(catalog, first, names, known)
        params = st.query_params
        if params.get("example") in catalog.examples:
            state["example_choice"] = params["example"]
            _load_example(catalog, params["example"], names, known)
            if params.get("assess") == "1" and readiness.ok:
                _assess(client, names)

    st.title("Draft review")
    st.caption(pres.SIMULATION_NOTE + " " + pres.RISK_NOTE)
    _readiness(readiness)
    _sidebar(catalog, names, known)

    st.header("Compose")
    moment = pres.parse_timestamp(state["f_timestamp"])
    _compose(catalog, names, moment)
    current = pres.build_request(_current_form(), names)
    current_fingerprint = pres.fingerprint(current)
    st.button(
        "Assess draft",
        key="assess",
        type="primary",
        disabled=not readiness.ok,
        on_click=_assess,
        args=(client, names),
        help=None if readiness.ok else "The scoring service is not ready.",
    )

    st.header("Result")
    view = pres.result_view(state["record"], current_fingerprint)
    _result(view, client)

    with st.expander(xp.exploration_title(exploration), expanded=False):
        _exploration_section(exploration, view)


def _readiness(readiness: pres.ReadinessView) -> None:
    if readiness.ok:
        st.success(readiness.headline)
        st.caption(" · ".join(f"{label}: {value}" for label, value in readiness.items))
    else:
        st.error(readiness.headline)
        if readiness.problem:
            st.caption(readiness.problem)


def _sidebar(catalog: ex.Catalog, names: dict[str, str], known: set[str]) -> None:
    state = st.session_state
    with st.sidebar:
        st.header("Curated examples")
        st.caption("Fictional validation drafts chosen by rule. Loading one replaces the draft in the form.")
        keys = list(catalog.examples)
        st.selectbox("Example", keys, key="example_choice", format_func=lambda key: catalog.examples[key].rule.title)
        st.button("Load example", key="load_example", on_click=_load_selected, args=(catalog, names, known))
        for key, reason in catalog.unmatched.items():
            st.caption(f"Example {key} is not available: {reason}")

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
    state = st.session_state
    st.text_input(
        "Draft timestamp",
        key="f_timestamp",
        help="ISO 8601 with a timezone, for example 2025-05-01T12:56:10Z. History strictly before it is used.",
    )
    if moment is None:
        st.caption("The timestamp does not parse with a timezone, so the directory below is not filtered. The service will reject it.")
    senders = ex.internal_senders(catalog.contacts, moment)["email_address"].tolist()
    if state["f_sender"] and state["f_sender"] not in senders:
        senders = [state["f_sender"]] + senders
    st.selectbox("Sender", senders, key="f_sender", format_func=lambda address: ex.contact_label(address, names))
    visible = ex.visible_contacts(catalog.contacts, moment)["email_address"].tolist()
    st.caption(f"The directory lists {len(visible)} fictional contacts visible at the draft timestamp.")
    columns = st.columns(3)
    for column, role in zip(columns, ROLES, strict=True):
        with column:
            selected = list(state[f"f_{role}"])
            options = selected + [item for item in visible if item not in selected]
            st.multiselect(role.capitalize(), options, key=f"f_{role}", format_func=lambda address: ex.contact_label(address, names))
            st.text_input(f"Other {role.capitalize()} addresses", key=f"f_{role}_other", help="Comma-separated. Typed addresses go to the service as written.")
    st.text_input("Subject", key="f_subject")
    st.text_area("Body", key="f_body", height=180)


def _result(view: pres.ResultView, client: api_client.ApiClient) -> None:
    if view.kind == "empty":
        st.info(view.headline)
        return
    if view.kind == "stale":
        st.warning(f"**{view.headline}** " + " ".join(view.detail))
        return
    if view.kind == "unable":
        st.error(f"**{view.headline}**")
        for line in view.detail:
            st.write(line)
        for note in view.notes:
            st.caption(note)
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
            name = f" ({row.display_name})" if row.display_name else ""
            st.markdown(f"**`{row.address}`**{name} · {', '.join(row.roles)} · risk score {row.risk_text} · {flag}")
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
