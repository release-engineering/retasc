# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cache

from ruamel.yaml import YAML


def yaml_str_representer(dumper, data):
    """Display nicer multi-line strings in YAML."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


@cache
def yaml() -> YAML:
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.map_indent = 2
    yaml.sequence_indent = 4
    yaml.sequence_dash_offset = 2
    yaml.sort_base_mapping_type_on_output = False  # type: ignore
    yaml.representer.add_representer(str, yaml_str_representer)
    return yaml
