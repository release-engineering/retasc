# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from unittest.mock import Mock

from pytest import fixture, raises

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.prerequisites.jira_issue import PrerequisiteJiraIssue
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.report import Report
from retasc.templates.template_manager import TemplateManager


def _mock_transitions(*status_names):
    """Create mock transition list from status names."""
    return [
        {"id": str(i), "name": f"To {s}", "to": s}
        for i, s in enumerate(status_names, 1)
    ]


@fixture
def mock_context():
    context = Mock()
    context.jira = Mock()
    context.jira.get_issue_transitions.return_value = _mock_transitions(
        "In Progress", "Closed"
    )
    context.template = TemplateManager(template_search_path=Path())
    context.report = Report()
    context.config = Mock()
    context.config.jira_label_prefix = "retasc-id-"
    context.config.from_jira_field_name = lambda x: x
    context.config.to_jira_field_name = lambda x: x
    context.config.jira_template_path = Path()
    context.template.params = {"jira_label_suffix": "-test"}
    yield context


def _make_issue(
    key="TEST-1",
    status_name="New",
    resolution=None,
    project_key="RHELWF",
    issue_type_name="Story",
):
    return {
        "key": key,
        "fields": {
            "resolution": resolution,
            "summary": "test",
            "labels": [],
            "status": {"name": status_name},
            "project": {"key": project_key},
            "issuetype": {"name": issue_type_name},
        },
    }


def test_status_transition_on_existing_issue(mock_context):
    """Transition an existing issue to a new status."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="In Progress",
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_called_once_with("TEST-1", "1")
    assert mock_context.report.current_data.get("status_transition") == "In Progress"


def test_status_already_at_target(mock_context):
    """No transition when issue is already at the desired status."""
    mock_context.jira.search_issues.return_value = [
        _make_issue(status_name="In Progress")
    ]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="In Progress",
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_not_called()
    assert "status_transition" not in mock_context.report.current_data


def test_status_transition_on_new_issue(mock_context):
    """Transition a newly created issue to the desired status."""
    mock_context.jira.search_issues.return_value = []
    mock_context.jira.create_issue.return_value = {"key": "TEST-2"}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={
            "summary": "test",
            "project": {"key": "RHELWF"},
            "issuetype": {"name": "Story"},
        },
        status="In Progress",
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_called_once_with("TEST-2", "1")


def test_status_unreachable_raises_error(mock_context):
    """Unreachable status raises PrerequisiteUpdateStateError."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}
    mock_context.jira.get_issue_transitions.return_value = []

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="Done",
    )

    with raises(PrerequisiteUpdateStateError, match="Cannot transition issue"):
        prereq.update_state(mock_context)


def test_status_jinja2_template(mock_context):
    """Status field supports Jinja2 template rendering."""
    mock_context.template.params["pipeline_run"] = Mock(is_finished=True)
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="{{ 'Closed' if pipeline_run.is_finished else 'In Progress' }}",
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_called_once_with("TEST-1", "2")
    assert mock_context.report.current_data.get("status_transition") == "Closed"


def test_status_transition_on_resolved_issue(mock_context):
    """Status transitions apply even to resolved issues."""
    mock_context.jira.search_issues.return_value = [
        _make_issue(status_name="Resolved", resolution={"name": "Done"})
    ]

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="Closed",
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.Completed
    mock_context.jira.transition_issue.assert_called_once_with("TEST-1", "2")


def test_no_status_field(mock_context):
    """Default behavior unchanged when no status field is set."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_not_called()


def test_direct_fallback_without_transitions(mock_context):
    """Direct single-step transition when no transitions list is provided."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="In Progress",
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_called_once_with("TEST-1", "1")


def test_multi_step_with_transitions(mock_context):
    """Multi-step transition using a transitions list."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}
    mock_context.jira.get_issue_transitions.side_effect = [
        _mock_transitions("In Progress"),
        _mock_transitions("Closed", "New"),
    ]

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="Closed",
        transitions=["In Progress"],
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    calls = mock_context.jira.transition_issue.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ("TEST-1", "1")
    assert calls[1].args == ("TEST-1", "1")
    assert mock_context.report.current_data.get("status_transition") == "Closed"


def test_transitions_skips_past_current_status(mock_context):
    """Transitions list skips entries at or before the current status."""
    mock_context.jira.search_issues.return_value = [
        _make_issue(status_name="In Progress")
    ]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}
    mock_context.jira.get_issue_transitions.return_value = _mock_transitions(
        "Code Review", "New"
    )

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="Code Review",
        transitions=["Refinement", "In Progress", "Code Review"],
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_called_once_with("TEST-1", "1")
    assert mock_context.report.current_data.get("status_transition") == "Code Review"


def test_empty_transitions_direct_only(mock_context):
    """Empty transitions list falls back to direct transition only."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="In Progress",
        transitions=[],
    )

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.jira.transition_issue.assert_called_once_with("TEST-1", "1")


def test_unreachable_with_transitions(mock_context):
    """Raises error when target is unreachable even with transitions list."""
    mock_context.jira.search_issues.return_value = [_make_issue(status_name="New")]
    mock_context.jira.get_issue.return_value = {"changelog": {"histories": []}}
    mock_context.jira.get_issue_transitions.return_value = _mock_transitions("Blocked")

    prereq = PrerequisiteJiraIssue(
        jira_issue="test-issue",
        template=None,
        fields={"summary": "test"},
        status="Closed",
        transitions=["In Progress"],
    )

    with raises(PrerequisiteUpdateStateError, match="Cannot transition issue"):
        prereq.update_state(mock_context)
