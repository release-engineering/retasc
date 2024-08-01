# SPDX-License-Identifier: GPL-3.0-or-later
import yaml

from retasc.validator.models import Rule


def validate_rule(rule_file: str):
    with open(rule_file) as file:
        rule_data = yaml.safe_load(file)
        validate_rule_dict(rule_data)


def validate_rule_dict(rule_data: dict):
    Rule(**rule_data)
