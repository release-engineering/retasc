# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

from pytest import fixture, mark, raises
from requests import Session
from requests.exceptions import ConnectionError, HTTPError

from retasc.models.config import Config
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.prerequisites.pipeline_run import PrerequisitePipelineRun
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.openshift_client import OpenShiftClient
from retasc.report import Report
from retasc.templates.template_manager import TemplateManager


@fixture
def mock_config(tmp_path):
    config = Mock(spec=Config)
    config.pipeline_run_template_path = tmp_path
    config.pipeline_run_name_prefix = "retasc-"
    config.pipeline_run_default_namespace = "default"
    config.openshift_api_url = "https://api.openshift.example.com"
    config.openshift_oc_image = "registry.example.com/origin-cli:latest"
    return config


@fixture
def mock_openshift():
    openshift = Mock(spec=OpenShiftClient)
    openshift.api_url = "https://api.openshift.example.com"
    openshift.get_pipeline_run.return_value = None
    openshift.get_config_map.return_value = None
    return openshift


@fixture
def mock_context(mock_config, mock_openshift):
    context = Mock()
    context.config = mock_config
    context.openshift = mock_openshift
    context.session = Session()
    context.template = TemplateManager(template_search_path=Path())
    context.template.params = {"pipeline_run_name_suffix": ""}
    context.report = Report()
    yield context


@fixture(autouse=True)
def template_file(tmp_path):
    template_file = tmp_path / "test.yml"
    template_file.write_text(
        dedent("""
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test
    """).strip()
    )
    yield template_file


@fixture
def prereq():
    return PrerequisitePipelineRun(
        pipeline_run="test-pipeline", template="test.yml", namespace="test-ns"
    )


def test_prerequisite_pipeline_run_validation_errors_no_openshift_url(tmp_path, prereq):
    config = Mock(spec=Config)
    config.pipeline_run_template_path = tmp_path
    config.openshift_api_url = None

    errors = prereq.validation_errors([], config)
    assert len(errors) == 1
    assert "openshift_api_url is not configured" in errors[0]


def test_prerequisite_pipeline_run_validation_errors_template_not_found(tmp_path):
    config = Mock(spec=Config)
    config.pipeline_run_template_path = tmp_path
    config.openshift_api_url = "https://api.openshift.example.com"

    prereq = PrerequisitePipelineRun(
        pipeline_run="test-pipeline",
        template="nonexistent.yml",
        namespace="test-ns",
    )
    errors = prereq.validation_errors([], config)
    assert len(errors) == 1
    assert "template file not found" in errors[0]


@mark.parametrize(
    ("result_status", "expected_state"),
    (
        ("Failed", ReleaseRuleState.InProgress),
        ("Succeeded", ReleaseRuleState.Completed),
        ("Completed", ReleaseRuleState.Completed),
    ),
)
def test_prerequisite_pipeline_run_result_exists(
    mock_context, prereq, result_status, expected_state
):
    mock_context.openshift.get_config_map.return_value = {
        "data": {"status": result_status}
    }

    state = prereq.update_state(mock_context)
    assert state == expected_state
    assert mock_context.report.data["pipeline_run"] == "test-pipeline"
    assert mock_context.report.data["status"] == result_status


@mark.parametrize(
    ("conditions", "expected_state", "expected_report_state"),
    (
        ([], ReleaseRuleState.InProgress, "Running"),
        ([{"type": "Running"}], ReleaseRuleState.InProgress, "Running"),
        (
            [{"type": "Succeeded", "status": "Unknown"}],
            ReleaseRuleState.InProgress,
            "Running",
        ),
        (
            [{"type": "Succeeded", "status": "True"}],
            ReleaseRuleState.Completed,
            "Succeeded",
        ),
        (
            [{"type": "Succeeded", "status": "False"}],
            ReleaseRuleState.InProgress,
            "Failed",
        ),
    ),
)
def test_prerequisite_pipeline_run_exists(
    mock_context, prereq, conditions, expected_state, expected_report_state
):
    mock_context.openshift.get_pipeline_run.return_value = {
        "metadata": {"name": "retasc-test-pipeline"},
        "status": {"conditions": conditions},
    }

    state = prereq.update_state(mock_context)
    assert state == expected_state
    assert mock_context.report.data["status"] == expected_report_state


def test_prerequisite_pipeline_run_create_new(mock_context, prereq):
    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    assert mock_context.report.data["status"] == "Created"
    assert mock_context.openshift.create_pipeline_run.called

    created_pipeline_run = mock_context.openshift.create_pipeline_run.call_args[0][0]
    assert created_pipeline_run["metadata"]["name"] == "retasc-test-pipeline"
    assert "finally" in created_pipeline_run["spec"]["pipelineSpec"]
    assert ["retasc-store-result"] == [
        task["name"] for task in created_pipeline_run["spec"]["pipelineSpec"]["finally"]
    ]


def test_prerequisite_pipeline_run_no_openshift_client(mock_context, prereq):
    mock_context.openshift = None

    with raises(
        PrerequisiteUpdateStateError, match="OpenShift client is not initialized"
    ):
        prereq.update_state(mock_context)


def test_prerequisite_pipeline_run_uses_default_namespace(mock_context):
    prereq = PrerequisitePipelineRun(pipeline_run="test-pipeline", template="test.yml")
    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.openshift.get_pipeline_run.assert_called_with(
        "retasc-test-pipeline", "default"
    )


def test_prerequisite_pipeline_run_no_namespace_configured(mock_context):
    mock_context.config.pipeline_run_default_namespace = None

    prereq = PrerequisitePipelineRun(pipeline_run="test-pipeline", template="test.yml")

    with raises(PrerequisiteUpdateStateError, match="No namespace specified"):
        prereq.update_state(mock_context)


def test_prerequisite_pipeline_run_result_check_error(mock_context, prereq):
    mock_context.openshift.get_config_map.side_effect = ConnectionError()

    with raises(PrerequisiteUpdateStateError, match="Failed to check result ConfigMap"):
        prereq.update_state(mock_context)


def test_prerequisite_pipeline_run_result_check_http_error(mock_context, prereq):
    mock_context.openshift.get_config_map.side_effect = HTTPError()

    with raises(PrerequisiteUpdateStateError, match="Failed to check result ConfigMap"):
        prereq.update_state(mock_context)


def test_prerequisite_pipeline_run_with_suffix(mock_context, prereq):
    mock_context.template.params["pipeline_run_name_suffix"] = "-test-suffix"

    state = prereq.update_state(mock_context)

    assert state == ReleaseRuleState.InProgress
    mock_context.openshift.get_pipeline_run.assert_called_with(
        "retasc-test-pipeline-test-suffix", "test-ns"
    )
