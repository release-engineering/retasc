# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from pytest import raises

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.prerequisites.target_date import PrerequisiteTargetDate
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.templates.template_manager import TemplateManager


def test_prerequisite_target_date_draft_schedule_reached():
    prereq = PrerequisiteTargetDate(target_date="start_date")
    expected_error = "Target date was reached, but schedule is marked as draft"

    context = Mock()
    context.template = TemplateManager(template_search_path=Path())
    today = datetime.now().date()
    context.template.params["start_date"] = today
    context.template.params["schedule_task_is_draft"] = True

    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(context)

    context.template.params["start_date"] = today + timedelta(days=1)
    assert prereq.update_state(context) == ReleaseRuleState.Pending
