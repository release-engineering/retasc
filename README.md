[![Coverage Status](https://coveralls.io/repos/github/release-engineering/retasc/badge.svg?branch=main)](https://coveralls.io/github/release-engineering/retasc?branch=main)

# Release Task Schedule Curator (ReTaSC)

ReTaSC is an app that plans product release work in Jira based on schedules in
Product Pages (PP).

## Introduction

ReTaSC is meant to run as a batch job regularly to monitor schedules in PP,
create/update Jira issues and run Tekton Pipelines (in a OpenShift/Kubernetes
cluster) according to custom rules and templates.

ReTaSC creates and manages Jira issues until resolved. This means that if a PP
schedule or a rule changes, the related unresolved Jira issues are also updated
and even closed.

## Tasks, Rules and Prerequisites

Tasks are objects managed by ReTaSC. Each Task is related to a specific Rule
and a Product Release (an identifier in PP).

Rules describe prerequisites to manage a Product Release.

Prerequisites are requirements that enhance template parameters and can block
Task completion if some conditions are not met.

Supported prerequisites:

- PP schedule item name, for example:
  `schedule_task: "GA for rhel {{ major }}.{{ minor }}"`
- a target date, for example: `target_date: "start_date - 3|weeks"`
- a condition, for example: `condition: "major >= 10"`
- reference to other Rule that must be in Completed state
- Jira issue templates - the issues are created only if none of the previous
  prerequisites are in Pending state
- Tekton PipelineRun templates - a Tekton Pipeline to run and monitor

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

For each task (rule and a given input), ReTaSC sets a unique label for the Jira
issues and a unique name for Tekton PipelineRuns, to find them later without
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

### Rule to Run a Tekton Pipeline

```yaml
name: New Release Configuration
prerequisites:
  - schedule_task: Set up new release
  - target_date: start_date - 1|week

  # Create a tracking Jira issue
  - jira_issue: new-release
    template: new-release.yml.j2

  # Wait for the start date
  - target_date: start_date - 1|day

  # Trigger the PipelineRun
  - pipeline_run: configure-new-release
    namespace: releng
    template: configure-new-release.yml.j2
```

### Rule to Process Items from HTTP API

The following rule fetches data from an HTTP API and creates a task for each item:

```yaml
name: Process Pending Builds from API
inputs:
  # Make an HTTP request and iterate over items in the JSON response
  - url: "https://api.example.com/builds"
    method: GET
    params:
    status: pending
    limit: 100
    # Extract array from nested JSON response using template expression
    # If the API returns: {"data": {"builds": [...]}}
    inputs: "http_data.data.builds"

prerequisites:
  # Skip builds that don't meet certain criteria
  - condition: "http_item.priority >= 5"

  # Create a Jira issue for each build
  - jira_issue: process-build
    template: "process-build.yml.j2"
    fields:
      summary: "Process build {{ http_item.name }} ({{ http_item.version }})"
      description: |
        Build ID: {{ http_item.id }}
        Priority: {{ http_item.priority }}
        Status: {{ http_item.status }}
```

The HTTP input provides the following template variables for each item:
- `http_item` - the current item from the JSON array
- `http_item_index` - the index of the current item (0-based)
- `http_response` - the full HTTP response object
- `http_data` - the parsed JSON response (useful in `inputs`)

The `inputs` supports various expressions:
- Simple key: `http_data.results`
- Nested access: `http_data.response.data.items`
- Bracket notation: `http_data['results']`
- Dynamic keys: `http_data[array_key]` (where `array_key` is a template variable)

### Rule to Process Old GitLab Merge Requests

The following rule monitors open merge requests on a GitLab server and creates
tracking issues for merge requests that have been open for more than 1 day:

```yaml
name: Review Stale Merge Requests
inputs:
  - url: "https://gitlab.example.com/api/v4/projects/hello%2fworld/merge_requests"
    method: GET
    params:
      state: opened
      scope: all
      author_username: retasc_bot
      created_before: "{{ now() - 1|day }}"
      # no draft MRs
      wip: "no"
    # NOTE: Passing tokens to rules is not supported yet. This would require
    #       using a safer storage than the configuration file.
    # headers:
    #   PRIVATE-TOKEN: "{{ config.gitlab_token }}"

prerequisites:
  # Create a tracking Jira issue for review
  - variable: jira_label_suffix
    string: "-{{ http_item.iid }}"
  - jira_issue: review-stale-mr
    template: "gitlab/review-stale-mr.yml.j2"
    fields:
      summary: "Review stale MR: {{ http_item.title }}"
      description: |
        Merge Request: {{ http_item.web_url }}
        Created: {{ http_item.created_at }}
        Project: {{ http_item.references.full }}

        This merge request has been open for {{ (today - date(http_item.created_at[:10])).days }} days.
      labels:
        - stale-merge-request
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
- `RETASC_JIRA_USERNAME` - Jira username used in basic
  authentication
- `RETASC_JIRA_PASSWORD` - Jira token used in basic authentication
- `RETASC_JIRA_TOKEN` - Jira access token, alternative to basic
  authentication
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
- `RETASC_OPENSHIFT_TOKEN` - OpenShift authentication token; optional; needed
  with `openshift_api_url` option for `pipeline_run` prerequisite to work
- `RETASC_PRODUCT_PAGES_COOKIES` - Optional. Path to a cookies file for Product
  Pages authentication using the current Kerberos ticket. If set, this is used
  instead of the OIDC authentication. Create the cookies file using the
  following `curl` command:

  ```
  kinit
  export RETASC_PRODUCT_PAGES_COOKIES=$PWD/pp_cookies.txt
  curl --negotiate --location-trusted -d "" -sLc $RETASC_PRODUCT_PAGES_COOKIES \
    https://product_pages.example.com/oidc/authenticate
  ```

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

Install uv with [pipx]:

```
# On macOS
brew install pipx
pipx ensurepath

# On Fedora
sudo dnf install pipx
pipx ensurepath

# Install uv
pipx install uv
```

Install and run the app to virtualenv with [uv]:

```
uv install
uv run retasc --help
```

Clean up the virtualenv (can be useful after larger host system updates):

```
uv venv --clear
```

[pipx]: https://pipx.pypa.io/stable/
[uv]: https://docs.astral.sh/uv/
