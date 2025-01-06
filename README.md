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
- In-progress (if some prerequisites are in In-progress but none are Pending)
- Completed (if all prerequisites are Completed)

## Environment Variables

Below is list of environment variables supported by the application and in the
container image:

- `RETASC_CONFIG` - Path to the main configuration file
- `RETASC_JIRA_TOKEN` - Jira access token
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
