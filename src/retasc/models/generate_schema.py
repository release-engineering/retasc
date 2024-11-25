# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sys
from typing import TextIO

import yaml

from retasc.models.config import Config
from retasc.models.rule import Rule


def _generate_schema(cls, file: TextIO, generator) -> None:
    schema = cls.model_json_schema()
    generator.dump(schema, file, indent=2, sort_keys=False)


def generate_schema(
    output_path: str | None, *, output_json: bool, config: bool = False
) -> None:
    generator = json if output_json else yaml
    cls = Config if config else Rule
    if output_path is None:
        _generate_schema(cls, sys.stdout, generator)
    else:
        with open(output_path, "w") as schema_file:
            _generate_schema(cls, schema_file, generator)
