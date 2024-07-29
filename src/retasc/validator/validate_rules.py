import logging

import yaml
from pydantic import ValidationError

from retasc.validator.models import Rule

logger = logging.getLogger(__name__)


def validate_rule(rule_file: str) -> bool:
    with open(rule_file) as file:
        rule_data = yaml.safe_load(file)
        return validate_rule_dict(rule_data)


def validate_rule_dict(rule_data: dict) -> bool:
    try:
        Rule(**rule_data)
        logger.info("The rule is valid.")
        return True
    except ValidationError as err:
        logger.error(f"The rule is invalid: {err}")
        return False
