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


@mark.parametrize(("arg", "issue_key"), (("run", "TEST"), ("dry-run", "DRYRUN")))
def test_run(arg, issue_key, capsys):
    run_main(arg, expected_exit_code=0)
    stdout, stderr = capsys.readouterr()
    assert stderr == ""
    expected_lines = [
        "ProductPagesRelease('rhel-10.0')",
        "  Example Rule",
        "    Condition('major >= 10')",
        "      result: True",
        "    Schedule('GA for rhel {{ major }}.{{ minor }}')",
        "    TargetDate('start_date - 7|days')",
        "      target_date: 1989-12-25",
        "    Rule('Dependent Rule 1')",
        "      Schedule('TASK')",
        "      TargetDate('start_date - 3|weeks')",
        "        target_date: 1989-12-13",
        "    Rule('Dependent Rule 2')",
        "      Schedule('TASK')",
        "      TargetDate('start_date - 2|weeks')",
        "        target_date: 1989-12-20",
        "    Jira('main_rhel-10.0')",
        '      create: {"project": {"key": "TEST"}, "summary": "Main Issue"}',
        f"      issue: {issue_key}-1",
        "      Subtask('add_beta_repos_rhel-10.0')",
        '        create: {"project": {"key": "TEST"}, "summary": "Add Beta Repos"}',
        f"        issue: {issue_key}-2",
        "      Subtask('notify_team_rhel-10.0')",
        '        create: {"project": {"key": "TEAM"}, "summary": "Notify Team"}',
        f"        issue: {issue_key}-3",
        "      state: InProgress",
        "    Jira('secondary_rhel-10.0')",
        '      create: {"project": {"key": "TEST"}, "summary": "Secondary Issue"}',
        f"      issue: {issue_key}-4",
        "      state: InProgress",
        "    state: InProgress",
        "  Dependent Rule 1",
        "    state: Completed",
        "  Dependent Rule 2",
        "    state: Completed",
    ]
    actual_lines = [
        line
        for line in stdout.split("\n")
        if line.startswith(" ") or line.startswith("ProductPagesRelease")
    ]
    assert expected_lines == actual_lines


def test_generate_schema_yaml(mock_generate_schema):
    run_main("generate-schema", "output_schema.yaml", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(
        "output_schema.yaml", output_json=False, config=False
    )


def test_generate_schema_yaml_to_stdout(mock_generate_schema):
    run_main("generate-schema", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(None, output_json=False, config=False)


def test_generate_schema_json(mock_generate_schema):
    run_main("generate-schema", "--json", "output_schema.json", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(
        "output_schema.json", output_json=True, config=False
    )


def test_generate_schema_json_to_stdout(mock_generate_schema):
    run_main("generate-schema", "--json", expected_exit_code=0)
    mock_generate_schema.assert_called_once_with(None, output_json=True, config=False)


def test_validate_rules_output(valid_rule_file, capsys):
    run_main("validate-rules", valid_rule_file, expected_exit_code=0)
    stdout, stderr = capsys.readouterr()
    assert "Validation succeeded: The rule files are valid" in stdout
    assert stderr == ""


def test_validate_invalid_rule_output(invalid_rule_file, capsys):
    run_main("validate-rules", invalid_rule_file, expected_exit_code=1)
    stdout, stderr = capsys.readouterr()
    assert "Validation failed: " in stdout
    assert "Invalid rule file" in stdout
    assert stderr == ""
