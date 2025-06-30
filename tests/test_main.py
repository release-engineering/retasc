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

    expected_lines = dedent("""
      ProductPagesReleases('rhel-10.0')
        Rule('Example Rule')
          Condition('major >= 10')
            result: True
          Schedule('GA for rhel {{ major }}.{{ minor }}')
            schedule_task: GA for rhel 10.0
          TargetDate('start_date - 7|days')
            target_date: 1989-12-25
          Rule('Dependent Rule 1')
            Schedule('TASK')
            TargetDate('start_date - 3|weeks')
              target_date: 1989-12-13
          Rule('Dependent Rule 2')
            Schedule('TASK')
            TargetDate('start_date - 2|weeks')
              target_date: 1989-12-20
          JiraIssue('main')
            issue_status: created
            issue_id: TEST-1
            Subtask('add_beta_repos')
              issue_status: created
              issue_id: TEST-2
            Subtask('notify_team')
              issue_status: created
              issue_id: TEST-3
            state: InProgress
          JiraIssue('secondary')
            issue_status: created
            issue_id: TEST-4
            state: InProgress
          TargetDate('end_date - 1|day')
            target_date: 1990-01-03
          JiraIssue('secondary')
            issue_status: created
            issue_id: TEST-5
            state: InProgress
          state: InProgress
        Rule('Dependent Rule 1')
          state: Completed
        Rule('Dependent Rule 2')
          state: Completed
    """).strip()
    expected_lines = expected_lines.replace("TEST-", f"{issue_key}-").split("\n")

    actual_lines = [
        line
        for line in stdout.split("\n")
        if line.startswith(" ") or line.startswith("ProductPagesReleases")
    ]

    assert expected_lines == actual_lines, stdout


@mark.parametrize("arg", ("run", "dry-run"))
def test_run_missing_schedule(arg, capsys, mock_pp):
    mock_pp.release_schedules.return_value = [
        task
        for task in mock_pp.release_schedules.return_value
        if task.name != "GA for rhel 10.0"
    ]
    expected_error = dedent("""
        ❌ Errors:
        ProductPagesReleases('rhel-10.0')
          Rule('Example Rule')
            Schedule('GA for rhel {{ major }}.{{ minor }}')
              Failed to find schedule task matching name 'GA for rhel 10.0'
    """).strip()
    run_main(arg, expected_exit_code=expected_error)
    stdout, stderr = capsys.readouterr()
    assert stderr == ""
    expected_lines = [
        "ProductPagesReleases('rhel-10.0')",
        "  Rule('Example Rule')",
        "    Condition('major >= 10')",
        "      result: True",
        "    Schedule('GA for rhel {{ major }}.{{ minor }}')",
        "      error: ❌ Failed to find schedule task matching name 'GA for rhel 10.0'",
        "      state: Pending",
        "    state: Pending",
        "  Rule('Dependent Rule 1')",
        "    Schedule('TASK')",
        "    TargetDate('start_date - 3|weeks')",
        "      target_date: 1989-12-13",
        "    state: Completed",
        "  Rule('Dependent Rule 2')",
        "    Schedule('TASK')",
        "    TargetDate('start_date - 2|weeks')",
        "      target_date: 1989-12-20",
        "    state: Completed",
    ]
    actual_lines = [
        line
        for line in stdout.split("\n")
        if line.startswith(" ") or line.startswith("ProductPagesReleases")
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
        "inputs": [
            {
                "type": "ProductPagesReleases",
                "release": "rhel-10.0",
                "rules": [
                    {
                        "rule": "Example Rule",
                        "prerequisites": ANY,
                        "state": "InProgress",
                    },
                    {
                        "rule": "Dependent Rule 1",
                        "state": "Completed",
                    },
                    {
                        "rule": "Dependent Rule 2",
                        "state": "Completed",
                    },
                ],
            }
        ],
    }
    prereq = data["inputs"][0]["rules"][0]["prerequisites"]
    assert prereq == [
        {
            "type": "Condition",
            "condition": "major >= 10",
            "result": True,
        },
        {"type": "Schedule", "schedule_task": "GA for rhel 10.0"},
        {
            "type": "TargetDate",
            "target_date_expr": "start_date - 7|days",
            "target_date": "1989-12-25",
        },
        {
            "type": "Rule",
            "rule": "Dependent Rule 1",
            "prerequisites": [
                {"type": "Schedule", "schedule_task": "TASK"},
                {
                    "type": "TargetDate",
                    "target_date_expr": "start_date - 3|weeks",
                    "target_date": "1989-12-13",
                },
            ],
        },
        {
            "type": "Rule",
            "rule": "Dependent Rule 2",
            "prerequisites": ANY,
        },
        {
            "type": "JiraIssue",
            "jira_issue": "main",
            "issue_data": ANY,
            "issue_status": "created",
            "issue_id": "DRYRUN-1",
            "subtasks": [
                {
                    "type": "Subtask",
                    "jira_issue": "add_beta_repos",
                    "issue_data": ANY,
                    "issue_status": "created",
                    "issue_id": "DRYRUN-2",
                },
                {
                    "type": "Subtask",
                    "jira_issue": "notify_team",
                    "issue_data": ANY,
                    "issue_status": "created",
                    "issue_id": "DRYRUN-3",
                },
            ],
            "state": "InProgress",
        },
        {
            "type": "JiraIssue",
            "jira_issue": "secondary",
            "issue_data": ANY,
            "issue_status": "created",
            "issue_id": "DRYRUN-4",
            "state": "InProgress",
        },
        {
            "type": "TargetDate",
            "target_date_expr": "end_date - 1|day",
            "target_date": "1990-01-03",
        },
        {
            "type": "JiraIssue",
            "jira_issue": "secondary",
            "issue_data": ANY,
            "issue_status": "created",
            "issue_id": "DRYRUN-5",
            "state": "InProgress",
        },
    ]
