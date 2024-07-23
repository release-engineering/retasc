# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy

import pytest
from pydantic import ValidationError
from pytest import raises

from retasc.validator.models import Rule
from retasc.validator.validate_rules import validate_rule


def test_rule_valid(valid_rule_file):
    try:
        validate_rule(str(valid_rule_file))
    except ValidationError:
        assert False, "A valid rule dict should not raise ValidationError"


def test_invalid_incorrect_days_before_or_after_type(valid_rule_dict):
    expected_error = r"days_before_or_after\s*Input should be a valid integer"
    invalid_rule_dict = deepcopy(valid_rule_dict)
    invalid_rule_dict["prerequisites"]["days_before_or_after"] = "invalid_type"

    with raises(ValidationError, match=expected_error):
        Rule(**invalid_rule_dict)


# By default, additional fields are ignored by pydantic
def test_unexpected_fields(valid_rule_dict):
    invalid_rule = deepcopy(valid_rule_dict)
    invalid_rule["unexpected_field"] = "unexpected_value"
    try:
        Rule(**invalid_rule)
    except ValidationError:
        pytest.fail(reason="ValidationError was raised unexpectedly.")


def test_incorrect_version_types(valid_rule_dict):
    expected_error = (
        r"version\n  Input should be a valid integer, "
        r"unable to parse string as an integer"
    )

    invalid_rule = deepcopy(valid_rule_dict)
    invalid_rule["version"] = "one"

    with raises(ValidationError, match=expected_error):
        Rule(**invalid_rule)


def test_missing_fields():
    expected_error = r"3 validation errors for Rule"
    invalid_rule = {
        "name": "Example Rule",
    }
    with raises(ValidationError, match=expected_error):
        Rule(**invalid_rule)
