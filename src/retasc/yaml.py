# SPDX-License-Identifier: GPL-3.0-or-later
from functools import cache

from ruamel.yaml import YAML


def yaml_str_representer(dumper, data):
    """Display nicer multi-line strings in YAML."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


@cache
def yaml() -> YAML:
    yaml = YAML(typ="safe")
    yaml.indent(sequence=4, offset=2)
    yaml.default_flow_style = False
    yaml.sort_base_mapping_type_on_output = False
    yaml.representer.add_representer(str, yaml_str_representer)
    return yaml
