# SPDX-License-Identifier: GPL-3.0-or-later
from pydantic import ValidationError
from pytest import raises

from retasc.validator.models import Rule


def test_invalid_incorrect_days_before_or_after_type(rule_dict):
    expected_error = r"days_before_or_after\s*Input should be a valid integer"
    rule_dict["prerequisites"]["days_before_or_after"] = "invalid_type"

    with raises(ValidationError, match=expected_error):
        Rule(**rule_dict)


# By default, additional fields are ignored by pydantic
def test_unexpected_fields(rule_dict):
    rule_dict["unexpected_field"] = "unexpected_value"
    Rule(**rule_dict)


def test_incorrect_version_types(rule_dict):
    expected_error = (
        r"version\n  Input should be a valid integer, "
        r"unable to parse string as an integer"
    )

    rule_dict["version"] = "one"

    with raises(ValidationError, match=expected_error):
        Rule(**rule_dict)


def test_missing_fields(rule_dict):
    del rule_dict["version"]
    with raises(ValidationError, match="Field required"):
        Rule(**rule_dict)
