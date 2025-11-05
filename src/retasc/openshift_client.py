# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from http import HTTPStatus
from typing import Any

from opentelemetry import trace
from requests import Session
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class OpenShiftClient:
    """OpenShift API Client"""

    def __init__(
        self,
        api_url: str,
        *,
        token: str,
        session: Session,
    ):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.session = session

    def _request(self, method: str, api_path: str, **kwargs) -> Any:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.api_url}{api_path}"
        response = self.session.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    @tracer.start_as_current_span("OpenShiftClient.get_pipeline_run")
    def get_pipeline_run(self, name: str, namespace: str) -> dict[str, Any] | None:
        """
        Get a PipelineRun by name and namespace, or None if not found.
        """
        api_path = f"/apis/tekton.dev/v1/namespaces/{namespace}/pipelineruns/{name}"

        try:
            return self._request("GET", api_path)
        except HTTPError as e:
            if (
                e.response is not None
                and e.response.status_code == HTTPStatus.NOT_FOUND
            ):
                return None
            raise

    @tracer.start_as_current_span("OpenShiftClient.create_pipeline_run")
    def create_pipeline_run(
        self, pipeline_run: dict[str, Any], namespace: str
    ) -> dict[str, Any]:
        """
        Create and return a PipelineRun object.
        """
        logger.info(
            "Creating PipelineRun %r in namespace %r",
            pipeline_run.get("metadata", {}).get("name"),
            namespace,
        )
        api_path = f"/apis/tekton.dev/v1/namespaces/{namespace}/pipelineruns"
        return self._request("POST", api_path, json=pipeline_run)

    @tracer.start_as_current_span("OpenShiftClient.get_config_map")
    def get_config_map(self, name: str, namespace: str) -> dict[str, Any] | None:
        """
        Get a ConfigMap by name in a namespace, or None if not found.
        """
        api_path = f"/api/v1/namespaces/{namespace}/configmaps/{name}"

        try:
            return self._request("GET", api_path)
        except HTTPError as e:
            if (
                e.response is not None
                and e.response.status_code == HTTPStatus.NOT_FOUND
            ):
                return None
            raise
