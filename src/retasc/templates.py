# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from typing import Any

import jinja2

type TemplateParams = dict[str, Any]


@dataclass
class TemplateManager:
    params: TemplateParams = field(default_factory=dict)

    def __init__(self):
        self.env = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            autoescape=True,
        )

    def __hash__(self):
        return hash(self.params)

    def render(self, template_text: str) -> str:
        """Renders a template text with params"""
        template = self.env.from_string(template_text)
        return template.render(self.params)

    def evaluate(self, expression: str) -> Any:
        """Evaluate expression with params"""
        expr = self.env.compile_expression(expression)
        return expr(self.params, undefined_to_none=False)
