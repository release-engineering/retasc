# SPDX-License-Identifier: GPL-3.0-or-later

from copy import deepcopy

from jinja2.exceptions import TemplateError
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema
from requests.exceptions import RequestException

from retasc.models.inputs import Input
from retasc.models.inputs.product_pages_releases import ProductPagesReleases
from retasc.models.prerequisites import Prerequisite
from retasc.models.prerequisites.exceptions import PrerequisiteUpdateStateError
from retasc.models.release_rule_state import ReleaseRuleState


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

    name: str = Field(description="The name of the rule.")
    inputs: list[Input] = Field(
        description="Inputs for the rule",
        default_factory=default_inputs,
    )
    prerequisites: list[Prerequisite] = Field(
        description="The prerequisites for the rule."
    )
    rule_file: SkipJsonSchema[str | None] = None

    def _process_prerequisite(self, prereq: Prerequisite, context) -> ReleaseRuleState:
        try:
            return prereq.update_state(context)
        except RequestException as e:
            context.report.add_request_error(e)
            return ReleaseRuleState.Pending
        except (PrerequisiteUpdateStateError, TemplateError) as e:
            context.report.add_error(str(e))
            return ReleaseRuleState.Pending

    def update_state(self, context) -> ReleaseRuleState:
        """
        The return value is:
        - Pending, if some prerequisites are in Pending
        - In-progress, if some prerequisites are in In-progress but none are Pending
        - Completed, if all prerequisites are Completed
        """
        context.report.current_data["rule"] = self.name

        params = context.rule_template_params.get(self.name)

        if params is not None:
            context.template.params.update(params)
            return params["state"]

        rule_state = ReleaseRuleState.Completed
        context.template.params["state"] = rule_state

        for prereq in self.prerequisites:
            context.template.params["rule_file"] = self.rule_file
            section = type(prereq).__name__.replace("Prerequisite", "")
            name = list(prereq.model_dump().values())[0]
            with context.report.section("prerequisites", type=section, name=name):
                state = self._process_prerequisite(prereq, context)
                if state != ReleaseRuleState.Completed:
                    context.report.set("state", state.name)

            rule_state = min(rule_state, state)
            context.template.params["state"] = rule_state

            if rule_state == ReleaseRuleState.Pending:
                break

        context.rule_template_params[self.name] = deepcopy(context.template.params)

        return rule_state
