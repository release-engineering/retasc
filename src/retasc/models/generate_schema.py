# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sys
from typing import TextIO

import yaml

from retasc.validator.models import Rule


def _generate_schema(file: TextIO, generator) -> None:
    schema = Rule.model_json_schema()
    generator.dump(schema, file, indent=2, sort_keys=False)


def generate_schema(output_path: str | None, *, output_json: bool) -> None:
    generator = json if output_json else yaml
    if output_path is None:
        _generate_schema(sys.stdout, generator)
    else:
        with open(output_path, "w") as schema_file:
            _generate_schema(schema_file, generator)
