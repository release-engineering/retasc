# SPDX-License-Identifier: GPL-3.0-or-later
import logging

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError

logger = logging.getLogger(__name__)


def _find_transition(transitions: list[dict], status: str) -> dict | None:
    """Find a transition targeting the given status."""
    return next((t for t in transitions if t["to"] == status), None)


def _find_next_transition(
    available: list[dict],
    desired_status: str,
    remaining: list[str],
) -> tuple[dict | None, list[str]]:
    """
    Pick the next transition to execute.

    Tries the target status first; if unavailable, picks the latest
    available intermediate from remaining (searching from the end).

    Returns a (transition, new_remaining) tuple, where new_remaining is
    the slice of the list after the chosen intermediate (or empty when
    the target status is reached directly).  transition is None when no
    suitable transition is available.
    """
    transition = _find_transition(available, desired_status)
    if transition is not None:
        return transition, []

    for i, status in enumerate(reversed(remaining)):
        transition = _find_transition(available, status)
        if transition is not None:
            return transition, remaining[len(remaining) - i :]

    return None, remaining


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
    remaining = (
        transitions[transitions.index(current_status) + 1 :]
        if current_status in transitions
        else transitions
    )

    visited = [current_status]
    while current_status != desired_status:
        available = context.jira.get_issue_transitions(issue["key"])
        transition, remaining = _find_next_transition(
            available, desired_status, remaining
        )
        if transition is None:
            available_names = [t["to"] for t in available]
            raise PrerequisiteUpdateStateError(
                f"Cannot transition issue {issue['key']} to {desired_status!r};"
                f" available transitions: {available_names}"
            )

        current_status = transition["to"]
        visited.append(current_status)
        logger.info(
            "Transitioning %r to %r via %r",
            issue["key"],
            current_status,
            transition["name"],
        )
        context.jira.transition_issue(issue["key"], transition["id"])

    context.report.set("status_transitions", visited)
