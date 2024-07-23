import yaml
import sys
from retasc.validator.models import Rule

def generate_schema(
    output_path="src/retasc/validator/schemas/rules_schema.yaml"
    ):
    schema = Rule.model_json_schema()
    schema_yaml = yaml.dump(schema, sort_keys=False)
    with open(output_path, "w") as schema_file:
        schema_file.write(schema_yaml)

if __name__ == "__main__":
    generate_schema(sys.argv[1])