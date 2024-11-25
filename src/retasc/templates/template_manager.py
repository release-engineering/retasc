# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jinja2

from .extensions import update_environment

type TemplateParams = dict[str, Any]


@dataclass
class TemplateManager:
    params: TemplateParams = field(default_factory=dict)

    def __init__(self, template_search_path: Path):
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_search_path),
            undefined=jinja2.StrictUndefined,
            autoescape=jinja2.select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=False,
            ),
        )
        update_environment(self.env)

    def render(self, template_text: str, **kwargs) -> str:
        """Render a template text with params"""
        template = self.env.from_string(template_text)
        return template.render(self.params, **kwargs)

    def evaluate(self, expression: str, **kwargs) -> Any:
        """Evaluate expression with params"""
        expr = self.env.compile_expression(expression, undefined_to_none=False)
        return expr(self.params, **kwargs)
