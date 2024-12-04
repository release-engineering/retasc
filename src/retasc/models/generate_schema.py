# SPDX-License-Identifier: GPL-3.0-or-later
import json
import sys
from typing import TextIO

from retasc.models.config import Config
from retasc.models.rule import Rule
from retasc.yaml import yaml


def json_dump(schema, file: TextIO):
    json.dump(schema, file, indent=2, sort_keys=False)


def yaml_dump(schema, file: TextIO):
    yaml().dump(schema, file)


def generate_schema(
    output_path: str | None, *, output_json: bool, config: bool = False
) -> None:
    generator = json_dump if output_json else yaml_dump
    cls = Config if config else Rule
    schema = cls.model_json_schema()
    if output_path is None:
        generator(schema, sys.stdout)
    else:
        with open(output_path, "w") as schema_file:
            generator(schema, schema_file)
