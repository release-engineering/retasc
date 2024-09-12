# SPDX-License-Identifier: GPL-3.0-or-later
import json

import yaml

from retasc.models.generate_schema import generate_schema
from retasc.models.rule import Rule


def test_generate_json_schema(tmp_path):
    schema_file = tmp_path / "rules_schema.json"
    generate_schema(output_path=schema_file, output_json=True)
    with open(schema_file) as f:
        schema = json.load(f)

    expected_schema = Rule.model_json_schema()
    assert schema == expected_schema


def test_generate_json_schema_to_stdout(tmp_path, capsys):
    generate_schema(output_path=None, output_json=True)
    stdout, stderr = capsys.readouterr()
    schema = json.loads(stdout)

    expected_schema = Rule.model_json_schema()
    assert schema == expected_schema

    assert stderr == ""


def test_generate_yaml_schema(tmp_path):
    schema_file = tmp_path / "rules_schema.yaml"
    generate_schema(output_path=schema_file, output_json=False)
    with open(schema_file) as f:
        schema = yaml.safe_load(f)

    expected_schema = Rule.model_json_schema()
    assert schema == expected_schema
