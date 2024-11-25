# SPDX-License-Identifier: GPL-3.0-or-later
from unittest.mock import Mock

from pydantic import ValidationError
from pytest import raises

from retasc.models.prerequisites.base import PrerequisiteBase
from retasc.models.rule import Rule


def test_prerequisite_base():
    base = PrerequisiteBase()
    assert base.validation_errors([], Mock()) == []
    with raises(NotImplementedError):
        base.update_state(Mock())
    with raises(NotImplementedError):
        base.section_name()


def test_invalid_prerequisite_type(rule_dict):
    rule_dict["prerequisites"].append(1)
    with raises(ValidationError, match="should be a valid dictionary"):
        Rule(**rule_dict)


def test_invalid_prerequisite_dict_key(rule_dict):
    rule_dict["prerequisites"].append({"test": "test"})
    with raises(ValidationError, match="Field required"):
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
