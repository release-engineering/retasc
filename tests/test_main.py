# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from unittest.mock import patch

from pytest import fixture, mark, raises

from retasc.__main__ import main


@fixture
def mock_generate_schema():
    with patch("retasc.__main__.generate_schema") as mock:
        yield mock


def run_main(*args, expected_exit_code=None):
    with patch.object(sys, "argv", ["retasc", *args]):
        with raises(SystemExit) as e:
            main()
        assert e.value.code == expected_exit_code


@mark.parametrize("arg", ("--help", "-h"))
def test_help(arg, capsys):
    run_main(arg, expected_exit_code=0)
    stdout, _ = capsys.readouterr()
    assert "ReTaSC" in stdout
    assert "--help" in stdout
    assert "-h" in stdout
    assert "--version" in stdout
    assert "-v" in stdout


@mark.parametrize("arg", ("--version", "-v"))
def test_version(arg, capsys):
    run_main(arg, expected_exit_code=0)
    stdout, _ = capsys.readouterr()
    assert "retasc" in stdout


def test_dummy_run(capsys):
    run_main(expected_exit_code=0)
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""


def test_generate_schema_yaml(mock_generate_schema):
    run_main("generate-schema", "output_schema.yaml", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(
        "output_schema.yaml", output_json=False
    )


def test_generate_schema_yaml_to_stdout(mock_generate_schema):
    run_main("generate-schema", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(None, output_json=False)


def test_generate_schema_json(mock_generate_schema):
    run_main("generate-schema", "--json", "output_schema.json", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with("output_schema.json", output_json=True)


def test_generate_schema_json_to_stdout(mock_generate_schema):
    run_main("generate-schema", "--json", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(None, output_json=True)


def test_validate_rule_output(valid_rule_file, capsys):
    run_main("validate-rule", valid_rule_file, expected_exit_code=0)
    stdout, stderr = capsys.readouterr()
    assert "Validation succeeded: The rule file is valid" in stdout
    assert stderr == ""


def test_validate_invalid_rule_output(invalid_rule_file, capsys):
    run_main("validate-rule", invalid_rule_file, expected_exit_code=1)
    stdout, stderr = capsys.readouterr()
    assert "Validation failed: The rule file is invalid" in stdout
    assert stderr == ""
