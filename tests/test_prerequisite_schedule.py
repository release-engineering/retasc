# SPDX-License-Identifier: GPL-3.0-or-later
import re
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from pytest import fixture, raises

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.templates.template_manager import TemplateManager


@fixture
def mock_context():
    context = Mock()
    context.template = TemplateManager(template_search_path=Path())
    context.template.params["release"] = "product-1.0"
    dummy_date = date(2025, 4, 10)
    context.pp.release_schedules.return_value = [
        ProductPagesScheduleTask(
            name=name,
            slug=f"product.{name}",
            start_date=dummy_date,
            end_date=dummy_date,
        )
        for name in ["test1", "test2", "other", "test2"]
    ]
    yield context


def test_prerequisite_schedule_task_or_slug_must_be_set(mock_context):
    expected = "Either schedule_task or schedule_slug must be set"
    with raises(ValueError, match=expected):
        PrerequisiteSchedule()


def test_prerequisite_schedule_slug(mock_context):
    prereq = PrerequisiteSchedule(schedule_slug="product.other")
    assert prereq.update_state(mock_context) == ReleaseRuleState.Completed


def test_prerequisite_schedule_nonunique_task(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="test2")
    expected_error = "Found multiple schedule tasks matching name 'test2'"
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


def test_prerequisite_schedule_nonunique_task_for_regexp(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="/test.*/")
    expected_error = (
        "Found multiple schedule tasks matching name '/test.*/'"
        ", matching are: 'test1', 'test2', 'test2'"
    )
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


def test_prerequisite_schedule_missing_task(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="test3")
    expected_error = "Failed to find schedule task matching name 'test3'"
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


def test_prerequisite_schedule_missing_task_skip(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="test3", skip_if_missing=True)
    assert prereq.update_state(mock_context) == ReleaseRuleState.Pending


def test_prerequisite_schedule_invalid_regex(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="/+/")
    expected_error = re.escape("Invalid regular expression pattern '+': ")
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


def test_prerequisite_schedule_invalid_regex_input_string(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="/test")
    expected_error = re.escape(
        "Regular expression string '/test' must be enclosed with"
        " slash character '/' on both sides."
    )
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


def test_prerequisite_schedule_allow_multiple(mock_context):
    slugs = [f"product.test_{i}" for i in range(3)]
    mock_context.pp.release_schedules.return_value.extend(
        ProductPagesScheduleTask(
            name="test",
            slug=slug,
            start_date=date(2025, 4 + i, 10),
            end_date=date(2025, 5 + i, 10),
            is_draft=(i == 2),
        )
        for i, slug in enumerate(slugs)
    )
    prereq = PrerequisiteSchedule(schedule_task="test", merge_multiple=True)
    assert prereq.update_state(mock_context) == ReleaseRuleState.Completed

    params = mock_context.template.params
    assert params["schedule_task"] == ["test"] * 3
    assert params["schedule_slug"] == slugs
    assert params["start_date"] == date(2025, 4, 10)
    assert params["end_date"] == date(2025, 7, 10)
    assert params["schedule_task_is_draft"] is True
