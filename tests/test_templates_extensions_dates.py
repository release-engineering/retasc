# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from pytest import fixture, mark

from retasc.templates.template_manager import TemplateManager


@fixture
def template_manager(tmp_path):
    """Create a TemplateManager with dates extension loaded."""
    return TemplateManager(template_search_path=tmp_path)


@fixture
def mock_datetime():
    with patch("retasc.templates.extensions.dates.datetime") as mock_datetime:
        mock_now = datetime(2025, 12, 2, 10, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now
        yield mock_datetime


class TestTemplateFilters:
    """Test that the new filters are available in templates."""

    def test_hours_filter(self, template_manager):
        """Test the hours filter in a template."""
        result = template_manager.render("{{ 2|hours }}")
        assert "2:00:00" in result

    def test_minutes_filter(self, template_manager):
        """Test the minutes filter in a template."""
        result = template_manager.render("{{ 45|minutes }}")
        assert "0:45:00" in result

    def test_seconds_filter(self, template_manager):
        """Test the seconds filter in a template."""
        result = template_manager.render("{{ 45|seconds }}")
        assert "0:00:45" in result

    def test_hour_filter_singular(self, template_manager):
        """Test the hour (singular) filter in a template."""
        result = template_manager.render("{{ 1|hour }}")
        assert "1:00:00" in result

    def test_minute_filter_singular(self, template_manager):
        """Test the minute (singular) filter in a template."""
        result = template_manager.render("{{ 1|minute }}")
        assert "0:01:00" in result

    def test_second_filter_singular(self, template_manager):
        """Test the second (singular) filter in a template."""
        result = template_manager.render("{{ 1|second }}")
        assert "0:00:01" in result

    @mark.parametrize(
        "template,expected_hours",
        [
            ("{{ now() + 1|hour }}", 1),
            ("{{ now() + 2|hours }}", 2),
            ("{{ now() - 3|hours }}", -3),
            ("{{ now() + 24|hours }}", 24),
            ("{{ datetime.fromisoformat('2025-12-02T10:00:00Z') + 1|hour }}", 1),
        ],
    )
    def test_now_plus_hours_filter(
        self, mock_datetime, template_manager, template, expected_hours
    ):
        """Test combining now() with hours filter."""
        result = template_manager.render(template)
        expected_time = mock_datetime.now() + timedelta(hours=expected_hours)
        assert expected_time.strftime("%Y-%m-%d %H:%M:%S") in result

    @mark.parametrize(
        "template,expected_minutes",
        [
            ("{{ now() + 30|minutes }}", 30),
            ("{{ now() + 60|minutes }}", 60),
            ("{{ now() - 15|minutes }}", -15),
            ("{{ now() + 1|minute }}", 1),
            ("{{ datetime.fromisoformat('2025-12-02T10:00:00Z') + 1|minute }}", 1),
        ],
    )
    def test_now_plus_minutes_filter(
        self, mock_datetime, template_manager, template, expected_minutes
    ):
        """Test combining now() with minutes filter."""
        result = template_manager.render(template)
        expected_time = mock_datetime.now() + timedelta(minutes=expected_minutes)
        assert expected_time.strftime("%Y-%m-%d %H:%M:%S") in result

    def test_combining_hours_and_minutes(self, mock_datetime, template_manager):
        """Test combining hours and minutes filters."""
        result = template_manager.render("{{ now() + 2|hours + 30|minutes }}")
        expected_time = mock_datetime.now() + timedelta(hours=2, minutes=30)
        assert expected_time.strftime("%Y-%m-%d %H:%M:%S") in result

    def test_datetime_formatting_with_strftime(self, mock_datetime, template_manager):
        """Test using the new functions with strftime for API date ranges."""
        template = """
        start: {{ (now() - 1|hours).strftime('%Y-%m-%dT%H:%M:%SZ') }}
        end: {{ now().strftime('%Y-%m-%dT%H:%M:%SZ') }}
        """
        mock_datetime.now.return_value = datetime(2025, 12, 2, 14, 30, 0, tzinfo=UTC)
        result = template_manager.render(template)
        assert "start: 2025-12-02T13:30:00Z" in result
        assert "end: 2025-12-02T14:30:00Z" in result
