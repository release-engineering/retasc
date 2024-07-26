import logging
import sys

import yaml
from pydantic import ValidationError

from retasc.retasc_logging import init_logging
from retasc.validator.models import Rule

init_logging()
logger = logging.getLogger(__name__)


def validate_rule(rule_file):
    with open(rule_file) as file:
        rule_data = yaml.safe_load(file)
        return validate_rule_dict(rule_data)


def validate_rule_dict(rule_data):
    try:
        Rule(**rule_data)
        logger.info("The rule is valid.")
        return True
    except ValidationError as err:
        logger.error(f"The rule is invalid: {err}")
        return False


if __name__ == "__main__":
    validate_rule(sys.argv[1])
