import sys
from runpy import run_module
from unittest.mock import patch

import yaml

from retasc.validator.generate_schema import generate_schema
from retasc.validator.models import Rule


def test_generate_schema(tmp_path):
    schema_file = tmp_path / "rules_schema.yaml"
    generate_schema(output_path=schema_file)
    with open(schema_file) as f:
        schema = yaml.safe_load(f)

    expected_schema = Rule.model_json_schema()
    assert schema == expected_schema


def test_generate_schema_script(tmp_path):
    schema_file = tmp_path / "rules_schema.yaml"

    with patch.object(sys, "argv", ["generate_schema", str(schema_file)]):
        run_module("retasc.validator.generate_schema", run_name="__main__")

    with open(schema_file) as f:
        schema = yaml.safe_load(f)

    expected_schema = Rule.model_json_schema()
    assert schema == expected_schema
