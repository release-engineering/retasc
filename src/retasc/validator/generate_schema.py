# SPDX-License-Identifier: GPL-3.0-or-later

import yaml

from retasc.validator.models import Rule


def generate_schema(output_path: str) -> None:
    schema = Rule.model_json_schema()
    schema_yaml = yaml.dump(schema, sort_keys=False)

    with open(output_path, "w") as schema_file:
        schema_file.write(schema_yaml)
