# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date
from unittest.mock import ANY, patch

from pytest import fixture

from retasc.product_pages_api import ProductPagesScheduleTask


@fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("RETASC_JIRA_URL", "")
    monkeypatch.setenv("RETASC_JIRA_TOKEN", "")
    monkeypatch.setenv("RETASC_PP_URL", "")
    monkeypatch.setenv("RETASC_RULES_PATH", "examples/rules")


@fixture(autouse=True)
def mock_jira():
    with patch("retasc.run.JiraClient", autospec=True) as mock:
        mock(ANY, ANY).search.return_value = []
        yield mock


@fixture(autouse=True)
def mock_pp():
    with patch("retasc.run.ProductPagesApi", autospec=True) as mock_cls:
        mock = mock_cls(ANY)
        mock.active_releases.return_value = ["rhel-10.0"]
        mock.release_schedules.return_value = {
            "GA for rhel 10.0": ProductPagesScheduleTask(
                start_date=date(1990, 1, 1),
                end_date=date(1990, 1, 2),
            ),
            "TASK": ProductPagesScheduleTask(
                start_date=date(1990, 1, 3),
                end_date=date(1990, 1, 4),
            ),
        }
        yield mock
