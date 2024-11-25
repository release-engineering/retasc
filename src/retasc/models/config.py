# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Config(BaseModel):
    rules_path: str = Field(description="Path to rules (processed recursively)")
    jira_template_path: Path = Field(
        description="Path to a root directory with Jira templates"
    )
    product_pages_url: str = Field(description="Product Pages URL")
    jira_url: str = Field(description="Jira URL")

    jira_label_templates: list[str] = Field(
        description=(
            "Label templates for the managed issues in Jira."
            ' Example: ["retasc-managed", "retasc-managed-{{ release }}"]'
        )
    )
    jira_label_prefix: str = Field(
        description="Prefix for labels identifying specific issue in Jira"
    )
    jira_fields: dict[str, str] = Field(
        description="Mapping from a property in Jira issue template file to a supported Jira field"
    )


def parse_config(config_path: str) -> Config:
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    return Config(**config_data)
