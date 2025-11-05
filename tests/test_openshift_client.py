# SPDX-License-Identifier: GPL-3.0-or-later
from pytest import fixture, raises
from requests import Session
from requests.exceptions import HTTPError

from retasc.openshift_client import OpenShiftClient


@fixture
def openshift_client():
    return OpenShiftClient(
        api_url="https://api.openshift.example.com",
        token="test-token",
        session=Session(),
    )


def test_openshift_client_init(openshift_client):
    assert openshift_client.api_url == "https://api.openshift.example.com"
    assert openshift_client.token == "test-token"


def test_get_pipeline_run_exists(openshift_client, requests_mock):
    pipeline_run = {
        "metadata": {"name": "test-pipeline"},
        "status": {"conditions": [{"type": "Succeeded", "status": "True"}]},
    }
    requests_mock.get(
        "https://api.openshift.example.com/apis/tekton.dev/v1/namespaces/test-ns/pipelineruns/test-pipeline",
        json=pipeline_run,
    )

    result = openshift_client.get_pipeline_run("test-pipeline", "test-ns")
    assert result == pipeline_run


def test_get_pipeline_run_not_found(openshift_client, requests_mock):
    requests_mock.get(
        "https://api.openshift.example.com/apis/tekton.dev/v1/namespaces/test-ns/pipelineruns/test-pipeline",
        status_code=404,
    )

    result = openshift_client.get_pipeline_run("test-pipeline", "test-ns")
    assert result is None


def test_get_pipeline_run_other_error(openshift_client, requests_mock):
    requests_mock.get(
        "https://api.openshift.example.com/apis/tekton.dev/v1/namespaces/test-ns/pipelineruns/test-pipeline",
        status_code=500,
    )

    with raises(HTTPError):
        openshift_client.get_pipeline_run("test-pipeline", "test-ns")


def test_create_pipeline_run(openshift_client, requests_mock):
    pipeline_run = {
        "apiVersion": "tekton.dev/v1",
        "kind": "PipelineRun",
        "metadata": {"name": "test-pipeline"},
    }
    created_pipeline = {**pipeline_run, "status": {}}

    requests_mock.post(
        "https://api.openshift.example.com/apis/tekton.dev/v1/namespaces/test-ns/pipelineruns",
        json=created_pipeline,
    )

    result = openshift_client.create_pipeline_run(pipeline_run, "test-ns")
    assert result == created_pipeline


def test_api_url_trailing_slash_removed():
    client = OpenShiftClient(
        api_url="https://api.openshift.example.com/",
        token="test-token",
        session=Session(),
    )
    assert client.api_url == "https://api.openshift.example.com"


def test_get_config_map_exists(openshift_client, requests_mock):
    config_map = {
        "metadata": {"name": "test-configmap"},
        "data": {"key": "value"},
    }
    requests_mock.get(
        "https://api.openshift.example.com/api/v1/namespaces/test-ns/configmaps/test-configmap",
        json=config_map,
    )

    result = openshift_client.get_config_map("test-configmap", "test-ns")
    assert result == config_map


def test_get_config_map_not_found(openshift_client, requests_mock):
    requests_mock.get(
        "https://api.openshift.example.com/api/v1/namespaces/test-ns/configmaps/test-configmap",
        status_code=404,
    )

    result = openshift_client.get_config_map("test-configmap", "test-ns")
    assert result is None


def test_get_config_map_other_error(openshift_client, requests_mock):
    requests_mock.get(
        "https://api.openshift.example.com/api/v1/namespaces/test-ns/configmaps/test-configmap",
        status_code=500,
    )

    with raises(HTTPError):
        openshift_client.get_config_map("test-configmap", "test-ns")
