# SPDX-License-Identifier: GPL-3.0-or-later
import logging

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError

logger = logging.getLogger(__name__)


def _remaining_transitions(transitions: list[str], current_status: str) -> list[str]:
    """
    Return items after current_status in the transitions list.

    If current_status is not found, return the full list.
    """
    try:
        idx = transitions.index(current_status)
        return transitions[idx + 1 :]
    except ValueError:
        return list(transitions)


def _find_transition(transitions: list[dict], status: str) -> dict | None:
    """Find a transition targeting the given status."""
    return next((t for t in transitions if t["to"] == status), None)


def _find_next_transition(
    available: list[dict],
    desired_status: str,
    remaining: list[str],
) -> dict | None:
    """
    Pick the next transition to execute.

    Tries the target status first; if unavailable, picks the latest
    available intermediate from remaining (searching from the end).
    """
    transition = _find_transition(available, desired_status)
    if transition is not None:
        return transition

    for status in reversed(remaining):
        transition = _find_transition(available, status)
        if transition is not None:
            return transition

    return None


def update_issue_status(
    issue: dict,
    status_template: str,
    transitions: list[str],
    context,
) -> None:
    """
    Transition a Jira issue to the desired status if needed.

    At each step the algorithm first attempts a direct transition to the
    target status.  If that is not available, it picks the latest
    (rightmost) status from the remaining intermediates that is offered
    as a Jira transition, executes it, and repeats.  Entries at or
    before the issue's current status are skipped automatically.

    :param issue: The Jira issue dict.
    :param status_template: Jinja2 template for the desired status.
    :param transitions: Ordered list of intermediate statuses to try
        when the target is not directly reachable.
    :param context: The execution context.
    :raises PrerequisiteUpdateStateError: If the desired status is unreachable.
    """
    desired_status = context.template.render(status_template)
    current_status = issue["fields"].get("status", {}).get("name", "")
    if current_status == desired_status:
        return

    remaining = _remaining_transitions(transitions, current_status)

    while True:
        available = context.jira.get_issue_transitions(issue["key"])
        transition = _find_next_transition(available, desired_status, remaining)
        if transition is None:
            available_names = [t["to"] for t in available]
            raise PrerequisiteUpdateStateError(
                f"Cannot transition issue {issue['key']} to {desired_status!r};"
                f" available transitions: {available_names}"
            )

        target = transition["to"]
        logger.info(
            "Transitioning %r to %r via %r",
            issue["key"],
            target,
            transition["name"],
        )
        context.jira.transition_issue(issue["key"], transition["id"])

        if target == desired_status:
            break

        remaining = _remaining_transitions(remaining, target)

    context.report.set("status_transition", desired_status)
