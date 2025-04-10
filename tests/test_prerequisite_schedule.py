# SPDX-License-Identifier: GPL-3.0-or-later
import re
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from pytest import fixture, raises

from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.prerequisites.schedule import PrerequisiteSchedule
from retasc.product_pages_api import ProductPagesScheduleTask
from retasc.templates.template_manager import TemplateManager


@fixture
def mock_context():
    context = Mock()
    context.template = TemplateManager(template_search_path=Path())
    context.template.params["release"] = "product-1.0"
    dummy_date = date(2025, 4, 10)
    context.pp.release_schedules.return_value = [
        ProductPagesScheduleTask(name=name, start_date=dummy_date, end_date=dummy_date)
        for name in ["test1", "test2", "other", "test2"]
    ]
    yield context


def test_prerequisite_schedule_nonunique_task(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="test2")
    expected_error = "Found multiple schedule tasks with name 'test2'"
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


def test_prerequisite_schedule_nonunique_task_for_regexp(mock_context):
    prereq = PrerequisiteSchedule(schedule_task="/test.*/")
    expected_error = (
        "Found multiple schedule tasks matching /test.*/"
        ", matching are: 'test1', 'test2', 'test2'"
    )
    with raises(PrerequisiteUpdateStateError, match=expected_error):
        prereq.update_state(mock_context)


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
