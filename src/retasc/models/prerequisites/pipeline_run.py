# SPDX-License-Identifier: GPL-3.0-or-later
from textwrap import dedent
from typing import Any

from pydantic import Field
from requests.exceptions import RequestException

from retasc.models.prerequisites.base import PrerequisiteBase
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState
from retasc.yaml import yaml

PIPELINE_RUN_DESCRIPTION = dedent("""
    Template for unique pipeline run name to identify the PipelineRun.

    The full name for the PipelineRun object will be in the format:
    {config.pipeline_run_name_prefix}{pipeline_run}{pipeline_run_name_suffix}
""").strip()

TEMPLATE_PATH_DESCRIPTION = dedent("""
    Path to the PipelineRun template YAML file
    relative to the "pipeline_run_template_path" configuration.
""").strip()


def _get_latest_pipeline_run_status(
    pipeline_run: dict[str, Any], condition_type: str
) -> str | None:
    status = pipeline_run.get("status")
    conditions = status and status.get("conditions") or []
    for condition in conditions:
        if condition.get("type") == condition_type:
            return condition.get("status")
    return None


def _rule_and_report_state_from_pipeline_run(
    pipeline_run: dict[str, Any],
) -> tuple[ReleaseRuleState, str]:
    status = _get_latest_pipeline_run_status(pipeline_run, "Succeeded")
    if status == "True":
        return ReleaseRuleState.Completed, "Succeeded"

    if status == "False":
        return ReleaseRuleState.InProgress, "Failed"

    return ReleaseRuleState.InProgress, "Running"


class PrerequisitePipelineRun(PrerequisiteBase):
    """
    Prerequisite PipelineRun.

    If the PipelineRun does not exist and no successful result is found,
    ReTaSC will create it by rendering and applying the template to the
    OpenShift cluster.

    The prerequisite state is InProgress until the PipelineRun completes
    successfully. After that, the state is Completed.

    Root directory for template files is indicated with "pipeline_run_template_path"
    option in ReTaSC configuration.

    The report and template variable "pipeline_run" will contain the following
    fields:
    - pipeline_run: Rendered from "pipeline_run" attribute
    - name: The full name of the PipelineRun object
    - namespace: The OpenShift namespace where the PipelineRun is created
    - is_completed: True only if the PipelineRun finished (succeeded or failed)
    - status: The current status of the PipelineRun or result
      (Created, Succeeded, Failed, or Running)

    The final PipelineRun result is stored in a ConfigMap object (with the same name),
    which is created by an extra finally task added to the PipelineRun.
    """

    pipeline_run: str = Field(description=PIPELINE_RUN_DESCRIPTION)
    template: str = Field(description=TEMPLATE_PATH_DESCRIPTION)
    namespace: str | None = Field(
        description="OpenShift namespace name (default from configuration)",
        default=None,
    )

    def validation_errors(self, rules, config) -> list[str]:
        errors = []

        template_file = config.pipeline_run_template_path / self.template
        if not template_file.is_file():
            errors.append(f"PipelineRun template file not found: {template_file}")

        if config.openshift_api_url is None:
            errors.append(
                "openshift_api_url is not configured but required for"
                " pipeline_run prerequisite"
            )

        return errors

    def _get_namespace(self, context) -> str:
        if self.namespace:
            return context.template.render(self.namespace)

        if context.config.pipeline_run_default_namespace:
            return context.config.pipeline_run_default_namespace

        raise PrerequisiteUpdateStateError(
            "No namespace specified and pipeline_run_default_namespace not configured"
        )

    def _pipeline_run_name(self, pipeline_run_id: str, context) -> str:
        suffix = context.template.params.get("pipeline_run_name_suffix", "")
        return f"{context.config.pipeline_run_name_prefix}{pipeline_run_id}{suffix}"

    def _render_pipeline_run_template(self, context) -> dict:
        template_file = context.config.pipeline_run_template_path / self.template

        with open(template_file) as f:
            template_content = f.read()

        content = context.template.render(template_content)
        return yaml().load(content)

    def _inject_finally_task(self, name: str, pipeline_run: dict, context) -> dict:
        """
        Inject a finally task to store the result.

        This is needed because the OpenShift cluster may not support Tekton Results.
        """
        result_task = {
            "name": "retasc-store-result",
            "params": [{"name": "aggregateTasksStatus", "value": "$(tasks.status)"}],
            "taskSpec": {
                "steps": [
                    {
                        "name": "create-result",
                        "image": context.config.openshift_oc_image,
                        "env": [
                            {
                                "name": "RETASC_PIPELINE_RUN_STATUS",
                                "value": "$(params.aggregateTasksStatus)",
                            }
                        ],
                        "script": dedent(f"""
                            #!/bin/bash
                            set -e
                            oc apply -f - <<EOF
                            apiVersion: v1
                            kind: ConfigMap
                            metadata:
                              name: {name!r}
                              labels:
                                retasc.io/result: "true"
                            data:
                              status: "$RETASC_PIPELINE_RUN_STATUS"
                            EOF
                        """).strip(),
                    }
                ]
            },
        }
        spec = pipeline_run.setdefault("spec", {})
        pipeline_spec = spec.setdefault("pipelineSpec", {})
        finally_tasks = pipeline_spec.setdefault("finally", [])
        finally_tasks.append(result_task)

        return pipeline_run

    def _result_status(self, name: str, namespace: str, context) -> str | None:
        """
        Return the result status from the ConfigMap if it exists, None otherwise.
        """
        try:
            config_map = context.openshift.get_config_map(name, namespace) or {}
            return config_map.get("data", {}).get("status")
        except RequestException as e:
            raise PrerequisiteUpdateStateError(f"Failed to check result ConfigMap: {e}")

    def update_state(self, context) -> ReleaseRuleState:
        """
        Return Completed only if the PipelineRun completed successfully or a
        successful result exists.

        If the PipelineRun does not exist and no result is found, it will be
        created and applied to the cluster.
        """
        if context.openshift is None:
            raise PrerequisiteUpdateStateError(
                "OpenShift client is not initialized. Ensure RETASC_OPENSHIFT_TOKEN is set."
            )

        pipeline_run_id = context.template.render(self.pipeline_run)
        namespace = self._get_namespace(context)
        name = self._pipeline_run_name(pipeline_run_id, context)

        context.report.set("pipeline_run", pipeline_run_id)
        context.report.set("name", name)
        context.report.set("namespace", namespace)

        result_status = self._result_status(name, namespace, context)
        is_completed = result_status is not None
        context.report.set("is_completed", is_completed)
        pipeline_run_template_vars = {
            "name": name,
            "namespace": namespace,
            "pipeline_run": pipeline_run_id,
            "status": result_status,
            "is_completed": is_completed,
        }
        context.template.params["pipeline_run"] = pipeline_run_template_vars

        if is_completed:
            context.report.set("status", result_status)
            if result_status in ("Succeeded", "Completed"):
                return ReleaseRuleState.Completed
            return ReleaseRuleState.InProgress

        pipeline_run = context.openshift.get_pipeline_run(name, namespace)
        if pipeline_run:
            rule_state, report_state = _rule_and_report_state_from_pipeline_run(
                pipeline_run
            )
            context.report.set("status", report_state)
            pipeline_run_template_vars["status"] = pipeline_run
            return rule_state

        pipeline_run_template = self._render_pipeline_run_template(context)
        pipeline_run_template.setdefault("metadata", {})["name"] = name
        pipeline_run_template = self._inject_finally_task(
            name, pipeline_run_template, context
        )

        context.openshift.create_pipeline_run(pipeline_run_template, namespace)
        context.report.set("status", "Created")
        pipeline_run_template_vars["status"] = "Created"

        return ReleaseRuleState.InProgress
