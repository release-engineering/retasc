# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy

from pydantic import ValidationError

from retasc.validator.validate_rules import validate_rule, validate_rule_dict


def assert_validation(rule, expected):
    try:
        validate_rule_dict(rule)
        assert expected is True
    except ValidationError:
        assert expected is False


def test_rule_dict_valid(valid_rule_dict):
    assert_validation(valid_rule_dict, True)


def test_rule_valid(valid_rule_file):
    try:
        validate_rule(str(valid_rule_file))
        assert True
    except ValidationError:
        assert False


def test_invalid_incorrect_days_before_or_after_type(valid_rule_dict):
    invalid_rule_dict = deepcopy(valid_rule_dict)
    invalid_rule_dict["prerequisites"]["days_before_or_after"] = "invalid_type"
    assert_validation(invalid_rule_dict, False)


# By default, additional fields are ignored by pydantic
def test_unexpected_fields(valid_rule_dict):
    invalid_rule = deepcopy(valid_rule_dict)
    invalid_rule["unexpected_field"] = "unexpected_value"
    assert_validation(invalid_rule, True)


def test_incorrect_version_types(valid_rule_dict):
    invalid_rule = deepcopy(valid_rule_dict)
    invalid_rule["version"] = "one"
    assert_validation(invalid_rule, False)


def test_missing_fields():
    invalid_rule = {
        "name": "Example Rule",
    }
    assert_validation(invalid_rule, False)
