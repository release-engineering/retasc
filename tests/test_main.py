# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from unittest.mock import patch

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
    run_main()
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""


@patch("retasc.__main__.validate_rule")
def test_validate_rule(mock_validate_rule, capsys):
    run_main("validate-rule", "test_rule.yaml")
    mock_validate_rule.assert_called_once_with("test_rule.yaml")
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""


@patch("retasc.__main__.generate_schema")
def test_generate_schema(mock_generate_schema, capsys):
    run_main("generate-schema", "output_schema.json")
    mock_generate_schema.assert_called_once_with("output_schema.json")
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""
