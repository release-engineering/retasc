# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sys
from textwrap import dedent
from unittest.mock import ANY, patch

from pytest import fixture, mark, raises

from retasc.__main__ import main


@fixture
def mock_generate_schema():
    with patch("retasc.__main__.generate_schema") as mock:
        yield mock


def run_main(*args, expected_exit_code: str | int = 0):
    with patch.object(sys, "argv", ["retasc", *args]):
        with raises(SystemExit) as e:
            main()
        assert e.value.code == expected_exit_code


@mark.parametrize("arg", ("--help", "-h"))
def test_help(arg, capsys):
    run_main(arg)
    stdout, _ = capsys.readouterr()
    assert "ReTaSC" in stdout
    assert "--help" in stdout
    assert "-h" in stdout
    assert "--version" in stdout
    assert "-v" in stdout


@mark.parametrize("arg", ("--version", "-v"))
def test_version(arg, capsys):
    run_main(arg)
    stdout, _ = capsys.readouterr()
    assert "retasc" in stdout


def test_dummy_run(capsys):
    run_main()
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""


@mark.parametrize(("arg", "issue_key"), (("run", "TEST"), ("dry-run", "DRYRUN")))
def test_run(arg, issue_key, capsys):
    run_main(arg)
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
        "    Jira('main')",
        '      create: {"project": {"key": "TEST"}, "summary": "Main Issue", "description": "Rule:examples/rules/rules.yaml Template:examples/jira/main.yaml.j2", "labels": ["retasc-id-main-rhel-10.0"]}',
        f"      issue: {issue_key}-1",
        "      Subtask('add_beta_repos')",
        '        create: {"project": {"key": "TEST"}, "summary": "Add Beta Repos", "labels": ["retasc-id-add_beta_repos-rhel-10.0"]}',
        f"        issue: {issue_key}-2",
        "      Subtask('notify_team')",
        '        create: {"project": {"key": "TEAM-RHEL"}, "summary": "Notify Team", "labels": ["notify-rhel-10.0", "retasc-id-notify_team-rhel-10.0"], "customfield_123": null}',
        f"        issue: {issue_key}-3",
        "      state: InProgress",
        "    Jira('secondary')",
        '      create: {"project": {"key": "TEST"}, "summary": "Secondary Issue", "labels": ["retasc-id-secondary-rhel-10.0"]}',
        f"      issue: {issue_key}-4",
        "      state: InProgress",
        "    TargetDate('end_date - 1|days')",
        "      target_date: 1990-01-03",
        "    Jira('secondary')",
        '      create: {"labels": ["test", "retasc-id-secondary-rhel-10.0"]}',
        f"      issue: {issue_key}-5",
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


@mark.parametrize("arg", ("run", "dry-run"))
def test_run_missing_schedule(arg, capsys, mock_pp):
    mock_pp.release_schedules.return_value = [
        task
        for task in mock_pp.release_schedules.return_value
        if task.name != "GA for rhel 10.0"
    ]
    expected_error = dedent("""
        ❌ Errors:
        ProductPagesRelease('rhel-10.0')
          Example Rule
            Schedule('GA for rhel {{ major }}.{{ minor }}')
              Failed to find schedule task with name 'GA for rhel 10.0'
    """).strip()
    run_main(arg, expected_exit_code=expected_error)
    stdout, stderr = capsys.readouterr()
    assert stderr == ""
    expected_lines = [
        "ProductPagesRelease('rhel-10.0')",
        "  Example Rule",
        "    Condition('major >= 10')",
        "      result: True",
        "    Schedule('GA for rhel {{ major }}.{{ minor }}')",
        "      error: ❌ Failed to find schedule task with name 'GA for rhel 10.0'",
        "      state: Pending",
        "    state: Pending",
        "  Dependent Rule 1",
        "    Schedule('TASK')",
        "    TargetDate('start_date - 3|weeks')",
        "      target_date: 1989-12-13",
        "    state: Completed",
        "  Dependent Rule 2",
        "    Schedule('TASK')",
        "    TargetDate('start_date - 2|weeks')",
        "      target_date: 1989-12-20",
        "    state: Completed",
    ]
    actual_lines = [
        line
        for line in stdout.split("\n")
        if line.startswith(" ") or line.startswith("ProductPagesRelease")
    ]
    assert expected_lines == actual_lines


def test_generate_schema_yaml(mock_generate_schema):
    run_main("generate-schema", "output_schema.yaml")
    mock_generate_schema.assert_called_once_with(
        "output_schema.yaml", output_json=False, config=False
    )


def test_generate_schema_yaml_to_stdout(mock_generate_schema):
    run_main("generate-schema")
    mock_generate_schema.assert_called_once_with(None, output_json=False, config=False)


def test_generate_schema_json(mock_generate_schema):
    run_main("generate-schema", "--json", "output_schema.json")
    mock_generate_schema.assert_called_once_with(
        "output_schema.json", output_json=True, config=False
    )


def test_generate_schema_json_to_stdout(mock_generate_schema):
    run_main("generate-schema", "--json")
    mock_generate_schema.assert_called_once_with(None, output_json=True, config=False)


def test_validate_rules_output(valid_rule_file, capsys):
    run_main("validate-rules", valid_rule_file)
    stdout, stderr = capsys.readouterr()
    assert "Validation succeeded: The rule files are valid" in stdout
    assert stderr == ""


def test_validate_invalid_rule_output(invalid_rule_file, capsys):
    run_main("validate-rules", invalid_rule_file, expected_exit_code=1)
    stdout, stderr = capsys.readouterr()
    assert "Validation failed: " in stdout
    assert "Invalid rule file" in stdout
    assert stderr == ""


def test_report_output_file(tmp_path):
    report = tmp_path / "report.json"
    run_main("dry-run", "--report", str(report))
    assert report.exists()
    data = json.loads(report.read_text())
    assert data == {
        "ProductPagesRelease('rhel-10.0')": {
            "Example Rule": {
                "prerequisites": ANY,
                "state": "InProgress",
            },
            "Dependent Rule 1": {
                "state": "Completed",
            },
            "Dependent Rule 2": {
                "state": "Completed",
            },
        },
    }
    prereq = data["ProductPagesRelease('rhel-10.0')"]["Example Rule"]["prerequisites"]
    assert prereq == [
        {
            "name": "Condition('major >= 10')",
            "result": True,
        },
        {
            "name": "Schedule('GA for rhel {{ major }}.{{ minor }}')",
        },
        {
            "name": "TargetDate('start_date - 7|days')",
            "target_date": "1989-12-25",
        },
        {
            "name": "Rule('Dependent Rule 1')",
            "prerequisites": [
                {
                    "name": "Schedule('TASK')",
                },
                {
                    "name": "TargetDate('start_date - 3|weeks')",
                    "target_date": "1989-12-13",
                },
            ],
        },
        {"name": "Rule('Dependent Rule 2')", "prerequisites": ANY},
        {
            "subtasks": [
                {
                    "name": "Subtask('add_beta_repos')",
                    "create": ANY,
                    "issue": "DRYRUN-2",
                },
                {
                    "name": "Subtask('notify_team')",
                    "create": ANY,
                    "issue": "DRYRUN-3",
                },
            ],
            "create": ANY,
            "issue": "DRYRUN-1",
            "name": "Jira('main')",
            "state": "InProgress",
        },
        {
            "create": ANY,
            "issue": "DRYRUN-4",
            "name": "Jira('secondary')",
            "state": "InProgress",
        },
        {
            "name": "TargetDate('end_date - 1|days')",
            "target_date": "1990-01-03",
        },
        {
            "create": ANY,
            "issue": "DRYRUN-5",
            "name": "Jira('secondary')",
            "state": "InProgress",
        },
    ]
