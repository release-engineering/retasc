import re
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

from pytest import fixture, mark, raises

from retasc.templates.template_manager import TemplateManager


@fixture
def fixtures():
    return Path(__file__).parent / "fixtures"


@mark.parametrize("extension_path", (".", "dunder.py"))
def test_template_extensions(fixtures, extension_path):
    template_search_path = fixtures / "templates"
    template_extensions = fixtures / "template_extensions" / extension_path
    manager = TemplateManager(
        template_search_path=template_search_path,
        template_extensions=[template_extensions],
    )
    txt_file = template_search_path / "test.yml.j2"
    template = txt_file.read_text()
    result = manager.render(template, test_variable="test")
    expected = dedent("""
        hello: world
        MONDAY: 0
        test: __test__
    """).strip()
    assert result == expected


def test_template_extensions_missing_function(fixtures):
    template_search_path = fixtures / "templates"
    expected = re.escape(
        "module 'retasc.templates.extensions.ext1.test_template'"
        " has no attribute 'update_environment'"
    )
    with raises(AttributeError, match=expected):
        TemplateManager(
            template_search_path=template_search_path,
            template_extensions=[Path(__file__)],
        )


@mark.parametrize(
    "mock_fn",
    (
        "importlib.util.spec_from_file_location",
        "importlib.util.module_from_spec",
    ),
)
def test_template_extensions_missing_file(fixtures, mock_fn):
    template_search_path = fixtures / "templates"
    expected = re.escape(f"Could not load extensions from {__file__}")
    with patch(mock_fn, return_value=None):
        with raises(RuntimeError, match=expected):
            TemplateManager(
                template_search_path=template_search_path,
                template_extensions=[Path(__file__)],
            )
