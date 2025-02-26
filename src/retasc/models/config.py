# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, Field

from retasc.yaml import yaml


class Config(BaseModel):
    rules_path: str = Field(description="Path to rules (processed recursively)")
    jira_template_path: Path = Field(
        description="Path to a root directory with Jira templates"
    )
    product_pages_url: str = Field(description="Product Pages URL")
    jira_url: str = Field(description="Jira URL")

    jira_label_prefix: str = Field(
        description="Prefix for labels identifying specific issue in Jira"
    )
    jira_fields: dict[str, str] = Field(
        description="Mapping from a property in Jira issue template file to a Jira field name"
    )

    connect_timeout: float = Field(
        description="HTTP connect timeout in seconds",
        default=15,
    )
    read_timeout: float = Field(
        description="HTTP read timeout in seconds",
        default=30,
    )
    jira_connect_timeout: float = Field(
        description="HTTP connect timeout in seconds, specific for Jira",
        default=15,
    )
    jira_read_timeout: float = Field(
        description="HTTP read timeout in seconds, specific for Jira",
        default=30,
    )

    def to_jira_field_name(self, field: str) -> str:
        """
        Convert human-readable field name (from configuration) to Jira field
        name (possibly something like "customfield_12345678").
        """
        return self.jira_fields.get(field, field)

    def from_jira_field_name(self, jira_field: str) -> str:
        """
        Convert Jira field name to human-readable field name.
        """
        return self._from_jira_field_name_map.get(jira_field, jira_field)

    @cached_property
    def _from_jira_field_name_map(self) -> dict[str, str]:
        return {v: k for k, v in self.jira_fields.items()}


def parse_config(config_path: str) -> Config:
    with open(config_path) as f:
        config_data = yaml().load(f)

    return Config(**config_data)
