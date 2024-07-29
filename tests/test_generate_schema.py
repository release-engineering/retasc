import pytest
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


def test_generate_schema_exception():
    with pytest.raises(Exception) as e:
        generate_schema(output_path=".")
    assert "Is a directory" in str(e.value)
