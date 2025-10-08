[![Coverage Status](https://coveralls.io/repos/github/release-engineering/retasc/badge.svg?branch=main)](https://coveralls.io/github/release-engineering/retasc?branch=main)

# Release Task Schedule Curator (ReTaSC)

ReTaSC is an app that plans product release work in Jira based on schedules in
Product Pages (PP).

## Introduction

ReTaSC is meant to run as a batch job regularly to monitor schedules in PP and
create or update Jira issues according to custom rules and Jira templates.

ReTaSC creates and manages Jira issues until resolved. This means that if a PP
schedule or a rule changes, the related unresolved Jira issues are also updated
and even closed.

## Tasks, Rules and Prerequisites

Tasks are objects managed by ReTaSC. Each Task is related to a specific Rule
and a Product Release (an identifier in PP).

Rules describe prerequisites to manage a Product Release.

Prerequisites are requirements that enhance template parameters and can block
Task completion if some conditions are not met. Here are some pre-defined
prerequisites:

- PP schedule item name, for example:
  `schedule_task: "GA for rhel {{ major }}.{{ minor }}"`
- a target date, for example: `target_date: "start_date - 3|weeks"`
- a condition, for example: `condition: "major >= 10"`
- reference to other Rule that must be in Completed state
- Jira issue templates - the issues are created only if none of the previous
  prerequisites are in Pending state

Task state can be one of:

- Pending (if some prerequisites are in Pending)
- InProgress (if some prerequisites are in InProgress but none are Pending)
- Completed (if all prerequisites are Completed)

## Rule Examples

### Simple Rule for New Product Releases

Here is an example of a single rule that would make sure that Jira issues
exists for specific releases in Product Pages:

```yaml
name: New RHEL release

# inputs for tasks created from this rule
inputs:
  # The input here is "rhel" product in Product Pages.
  # One task will be created for each active release of the product.
  - product: rhel

# prerequisites are processed in the given order
prerequisites:
  # The following condition skips releases with version less than 10.1.
  # For example, for rhel-9.2, the no other prerequisites would be processed,
  # and the task would be marked as Pending.
  - condition: "(10, 1) <= (major, minor)"

  # Require schedule task with "GA" name to be defined (for all releases
  # rhel-10.1 and up). This also sets a few variables for templating engine,
  # mainly "start_date" and "end_date".
  - schedule_task: "GA"

  # Avoid processing further prerequisites if the target date is not reached,
  # or the schedule task is marked as draft (this can be overridden with
  # "ignore_drafts"). Processing would continue 8 weeks before the start date
  # in "GA" schedule (and the schedule is not draft).
  - target_date: "start_date - 8|weeks"

  # This would create and manage Jira issues (main one and sub tasks) until
  # the main issue one is resolved.
  - jira_issue: rhel_config
    # Jira issue fields are defined in Jinja2 template (the file path is
    # relative to "jira_template_path" in configuration).
    template: "rhel/rhel_config.yml.j2"
    # The fields can be also defined or overridden here (both "template" and
    # "fields" are optional).
    fields:
      labels:
        - releng
    subtasks:
      - id: rhelwf-release-handoff-{{ release }}
        template: "rhelwf/new-rhel-release/set-up-rhel-release-phase1-accept-handoff.yml.j2"
        fields:
          priority:
            name: Normal

  # After creating Jira issues, the task is marked as InProgress until the main Jira
  # issue is resolved. After that, the task is marked as Completed.
```

Using the rule above, ReTaSC would create a Jira issue (and a subtask) after
`target_date` and update it whenever some fields change in the template.

ReTaSC sets a unique label for the Jira issues, to find it later without
storing any extra information. The label is constructed using
"jira_label_prefix" configuration, "jira_issue" from the prerequisite and
"jira_label_suffix" template variable originating from the Product pages input.

### Rule to Create a Jira Issue on a Fixed Date

The following rule will create a Jira 2 weeks before a target date:

```yaml
name: Enable XYZ Release on 2025.07.17
inputs:
  - variables:
      date: date('2025-07-17')
prerequisites:
  - condition: today < date
  - target_date: date - 2|weeks
  - jira_issue: enable_xyz_release
    template: "enable-xyz-release.yml.j2"
    fields:
      duedate: "{{ date }}"
```

## Templating Engine

Some variable and files are evaluated by Jinja2 templating engine.

Template variables:

- `config` - ReTaSC configuration
- `report` - contains data for the final report
- `report.state` - current state being updated when prerequisites are
  processed; can be "Pending", "InProgress" or "Completed"
- `report.result` - result from the last `condition` prerequisite
- `today` - today's date in UTC (Python `date` object)
- `rule_file` - current rule file path
- `jira_issues` - dict of managed Jira issues; key is Jira issue ID
- `jira_template_file` - Jira issue template path, available only in Jira
  template prerequisites

There are also `days`, `day`, `weeks` and `week` filters for creating Python
`timedelta` objects for date manipulation. For example: `today + 1|day` or
`today + 2|days`, `start_date +2|weeks`. Note: Singular and plural versions
work the same and take any integer as an argument. So both `2|day` and `1|days`
would work.

### Custom Templating Extensions

Custom extensions can be added to the templating engine to support additional
variables, filters and functions.

To add custom extensions, add paths to the `template_extensions` configuration
file. Each path must point to a Python file or a directory with the extensions.

The extension is a Python file that includes the `update_environment` function
that takes the `jinja2.Environment` as an argument. For example:

```python
def update_environment(env):
    env.globals["custom_var"] = "This is a custom variable"
    env.globals["custom_fn"] = lambda a, b: f"{a}.{b}"
    env.filters["dunder"] = lambda value: f"__{value}__"
```

## Environment Variables

Below is list of environment variables supported by the application and in the
container image:

- `RETASC_CONFIG` - Path to the main configuration file
- `RETASC_JIRA_TOKEN` - Jira access token
- `RETASC_OIDC_CLIENT_ID`, `RETASC_OIDC_CLIENT_SECRET` - OIDC client ID and
  secret to access Product Pages (`oidc_token_url` must be set in the
  configuration)
- `RETASC_LOGGING_CONFIG` - Path to JSON file with the logging configuration;
  see details in [Configuration dictionary
  schema](https://docs.python.org/3/library/logging.config.html#logging-config-dictschema)
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` - OpenTelemetry exporter endpoint; if
  unset (default), traces are not exported; for example:
  `https://jaeger.example.com:4318/v1/traces`
- `OTEL_EXPORTER_SERVICE_NAME` - service name for OpenTelemetry; if unset
  (default), traces are not exported

## Validate Rule Files

The ReTaSC project includes a validator to ensure that rule files are correctly
formatted and adhere to the expected schema (see the section below).

Example of validating rule files with CLI:

```bash
export RETASC_CONFIG=examples/config.yaml

# validate all rules in a path recursively
retasc validate-rules examples/rules

# or validate single file
retasc validate-rules examples/rules/rules.yaml
```

## Generate Schema Files

Examples of generating YAML and JSON schema for rule and configuration files:

```
retasc generate-schema rule_schema.yaml
retasc generate-schema --json rule_schema.json
retasc generate-schema --config --json config.json
```

## Development

This section lists useful commands to help with ReTaSC development.

Install pre-commit locally:

```
pre-commit install
```

Creating a new commit or amending an existing commit may cause the pre-commit
to fail. In many cases pre-commit automatically fixes formatting and you can
run the command again:

```
> git commit --ammend --no-edit
...
autoflake................................................................Failed
- hook id: autoflake
- files were modified by this hook
...

> git commit --ammend --no-edit
...
autoflake................................................................Passed
...
```

Run tests and additional linters:

```
tox
```

Inspect specific test failure:

```
tox -e py3 -- --no-cov -lvvvvsxk test_init_tracing_with_valid_config
```

Install poetry with [pipx]:

```
# On macOS
brew install pipx
pipx ensurepath

# On Fedora
sudo dnf install pipx
pipx ensurepath

# Install poetry
pipx install poetry
```

Install and run the app to virtualenv with [Poetry]:

```
poetry install
poetry run retasc --help
```

Clean up the virtualenv (can be useful after larger host system updates):

```
poetry env remove --all
```

If you are not familiar with those please watch this [Tutorial] to have some ideas on what are
poetry, pre-commit, flake, tox, etc...

[pipx]: https://pipx.pypa.io/stable/
[Poetry]: https://python-poetry.org/docs/
[Tutorial]: https://www.linkedin.com/learning/create-an-open-source-project-in-python
