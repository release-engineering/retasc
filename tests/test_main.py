# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from unittest.mock import patch

from pydantic import ValidationError
from pytest import mark, raises

from retasc.__main__ import main


def run_main(*args, code=None):
    with patch.object(sys, "argv", ["retasc", *args]):
        if code is None:
            main()
            return

        with raises(SystemExit) as e:
            main()
        assert e.value.code == code


@mark.parametrize("arg", ("--help", "-h"))
def test_help(arg, capsys):
    run_main(arg, code=0)
    stdout, _ = capsys.readouterr()
    assert "ReTaSC" in stdout
    assert "--help" in stdout
    assert "-h" in stdout
    assert "--version" in stdout
    assert "-v" in stdout


@mark.parametrize("arg", ("--version", "-v"))
def test_version(arg, capsys):
    run_main(arg, code=0)
    stdout, _ = capsys.readouterr()
    assert "retasc" in stdout


def test_dummy_run(capsys):
    run_main(code=0)
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""


@patch("retasc.__main__.validate_rule")
def test_validate_rule(mock_validate_rule):
    run_main("validate-rule", "any_valid_rule.yaml", code=0)
    mock_validate_rule.assert_called_once_with("any_valid_rule.yaml")


@patch("retasc.__main__.validate_rule")
def test_validate_invalid_rule(mock_validate_rule):
    mock_validate_rule.side_effect = ValidationError.from_exception_data(
        title="mocked", line_errors=[]
    )
    run_main("validate-rule", "any_invalid_rule.yaml", code=1)
    mock_validate_rule.assert_called_once_with("any_invalid_rule.yaml")


@patch("retasc.__main__.generate_schema")
def test_generate_schema(mock_generate_schema):
    run_main("generate-schema", "output_schema.json", code=0)
    mock_generate_schema.assert_called_once_with("output_schema.json")
