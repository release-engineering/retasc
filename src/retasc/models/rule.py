# SPDX-License-Identifier: GPL-3.0-or-later

from copy import deepcopy

import jinja2.exceptions
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from retasc.models.inputs import Input
from retasc.models.inputs.product_pages_releases import ProductPagesReleases
from retasc.models.prerequisites import Prerequisite
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState

SCHEMA_VERSION = 1


def default_inputs() -> list[Input]:
    return [ProductPagesReleases(product="rhel")]


class Rule(BaseModel):
    """
    Rule with prerequisites.

    The rule provides a state based on specific input (product, release,
    version etc.) passed to the prerequisites:
    - Pending, if some prerequisites are in Pending
    - In-progress, if some prerequisites are in In-progress but none are Pending
    - Completed, if all prerequisites are Completed

    Prerequisites are processed only until the first one in Pending state.
    """

    model_config = ConfigDict(frozen=True)

    version: int = Field(
        description=f"The version of the rule schema. The latest version is {SCHEMA_VERSION}."
    )
    name: str = Field(description="The name of the rule.")
    inputs: list[Input] = Field(
        description="Inputs for the rule",
        default_factory=default_inputs,
    )
    prerequisites: list[Prerequisite] = Field(
        description="The prerequisites for the rule."
    )
    rule_file: SkipJsonSchema[str | None] = None

    def update_state(self, context) -> ReleaseRuleState:
        """
        The return value is:
        - Pending, if some prerequisites are in Pending
        - In-progress, if some prerequisites are in In-progress but none are Pending
        - Completed, if all prerequisites are Completed
        """
        params = context.rule_template_params.get(self.name)
        if params is not None:
            context.template.params.update(params)
            return params["state"]

        rule_state = ReleaseRuleState.Completed
        context.template.params["state"] = rule_state

        for prereq in self.prerequisites:
            context.template.params["rule_file"] = self.rule_file
            with context.report.section(prereq.section_name(context)):
                try:
                    state = prereq.update_state(context)
                except (
                    PrerequisiteUpdateStateError,
                    jinja2.exceptions.TemplateError,
                ) as e:
                    context.report.add_error(str(e))
                    state = ReleaseRuleState.Pending

                if state != ReleaseRuleState.Completed:
                    context.report.set("state", state.name)

            rule_state = min(rule_state, state)
            context.template.params["state"] = rule_state

            if rule_state == ReleaseRuleState.Pending:
                break

        context.rule_template_params[self.name] = deepcopy(context.template.params)

        return rule_state
