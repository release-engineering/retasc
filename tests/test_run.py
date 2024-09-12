from unittest.mock import patch

from pytest import fixture


@fixture
def mock_jira():
    with patch("retasc.run.JiraClient") as mock:
        mock.search.return_value = []
        yield mock


@fixture
def mock_pp():
    with patch("retasc.run.ProductPagesApi") as mock:
        yield mock


def test_create_issue():
    pass


def test_drop_issue_when_rule_is_removed():
    pass


def test_update_issue_when_pp_date_changes():
    pass
