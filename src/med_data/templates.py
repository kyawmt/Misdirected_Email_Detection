"""Topic templates for fictional mail.

Every non-empty body includes a unique Ref token. Marker phrases are present
in each template of that topic so checks can confirm topic identity without
treating the marker as a label.
"""

TOPIC_MARKERS = {
    "staffing": "headcount",
    "office_equipment": "laptop",
    "facilities": "badge",
    "purchase_scheduling": "purchase order",
    "budget": "cost center",
    "compensation": "salary band",
    "kickoff": "kickoff",
    "introduction": "introduction",
    "project_update": "project status",
}

REPLY_PHRASES = {
    "staffing": "headcount note",
    "office_equipment": "laptop request",
    "facilities": "badge request",
    "purchase_scheduling": "purchase order update",
    "budget": "cost center update",
    "compensation": "salary band note",
    "kickoff": "kickoff note",
    "introduction": "introduction note",
    "project_update": "project status note",
    "little_text": "short note",
}

_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "staffing": [
        (
            "Headcount update for {week}",
            "Hi {to_names},\n\n"
            "Sharing the headcount update for {week}. Ticket {ticket} tracks two open roles and the candidates in final interviews. Please review the slate before Friday.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Candidate slate {ticket}",
            "Hi {to_names},\n\n"
            "The staffing slate for {week} is ready. Headcount ticket {ticket} still has one role waiting on a panel. Send any holds today.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "office_equipment": [
        (
            "Laptop request {ticket}",
            "Hi {to_names},\n\n"
            "Please order a laptop under ticket {ticket} for the desk move on {week}. Include a monitor only if the desk audit shows a gap.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Equipment refresh {week}",
            "Hi {to_names},\n\n"
            "The workplace refresh for {week} needs one replacement laptop. Ticket {ticket} has the desk and asset tag.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "facilities": [
        (
            "Badge access for {week}",
            "Hi {to_names},\n\n"
            "Please update badge access before {week}. Ticket {ticket} lists the meeting room and the people who need entry during the maintenance window.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Meeting room holds {ticket}",
            "Hi {to_names},\n\n"
            "Facilities ticket {ticket} covers badge readers and meeting room holds for {week}. Confirm the seating plan when you can.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "purchase_scheduling": [
        (
            "Purchase order delivery {ticket}",
            "Hi {to_names},\n\n"
            "Checking the purchase order delivery window for {week}. Ticket {ticket} is the shipment we already scheduled with you.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Shipment window {week}",
            "Hi {to_names},\n\n"
            "The purchase order for ticket {ticket} should leave the warehouse during {week}. Reply if the dock time needs to move.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "budget": [
        (
            "Cost center forecast {week}",
            "Hi {to_names},\n\n"
            "Attached in prose: the cost center forecast for {week}. Ticket {ticket} flags one variance in the project budget. Please confirm the figure before the review.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Forecast variance {ticket}",
            "Hi {to_names},\n\n"
            "The {week} cost center review is open. Ticket {ticket} compares the project forecast with the latest actuals.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "compensation": [
        (
            "Salary band planning {week}",
            "Hi {to_names},\n\n"
            "For the {week} compensation cycle, salary band notes are in ticket {ticket}. Please keep this within the people team and confirm the planning figures.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Compensation planning {ticket}",
            "Hi {to_names},\n\n"
            "Salary band adjustments for {week} are listed under ticket {ticket}. This compensation draft is for the people partners on the thread.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "kickoff": [
        (
            "Kickoff for the new workstream",
            "Hi {to_names},\n\n"
            "I am inviting you to the kickoff for a new workstream starting {week}. Ticket {ticket} has the charter and the first agenda. Your facilities context will help the room plan, and this invitation is intentional.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Workstream kickoff {week}",
            "Hi {to_names},\n\n"
            "Please join the kickoff on {week}. Ticket {ticket} is the new workstream charter. I want you in the meeting because the room plan depends on your team.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "project_update": [
        (
            "Project status for {week}",
            "Hi {to_names},\n\n"
            "The project status for {week} is on ticket {ticket}. One milestone moved, and the rest of the plan is unchanged. Please reply with blockers.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Weekly project status {ticket}",
            "Hi {to_names},\n\n"
            "Sharing this week's project status. Ticket {ticket} covers the {week} milestone and the open questions for the group.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
    "introduction": [
        (
            "Introduction for {week}",
            "Hi {to_names},\n\n"
            "This is an introduction to the project. We are starting work the week of {week} and ticket {ticket} has the brief. I am writing so we can collaborate from the start.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
        (
            "Welcome and introduction {ticket}",
            "Hi {to_names},\n\n"
            "Welcome. This introduction covers how we will work together from {week}. Ticket {ticket} has the goals and the first milestone.\n\n"
            "Thanks,\n{sender_name}\nRef: {ref}",
        ),
    ],
}


def render(topic: str, rng, **slots: str) -> tuple[str, str]:
    choices = _TEMPLATES[topic]
    index = int(rng.integers(0, len(choices)))
    subject, body = choices[index]
    return subject.format(**slots), body.format(**slots)


def render_reply(topic: str, rng, **slots: str) -> tuple[str, str]:
    phrase = REPLY_PHRASES[topic]
    # Burn one draw so each reply has its own place in the seed stream.
    _ = int(rng.integers(0, 2))
    subject = "Re: {subject}".format(**slots)
    body = (
        "Thanks {sender_name}. I recorded the {phrase} from {week}.\n\n"
        "Ack {ref}"
    ).format(phrase=phrase, **slots)
    return subject, body
