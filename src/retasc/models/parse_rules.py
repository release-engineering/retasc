# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from glob import iglob
from itertools import chain

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError

from retasc.models.config import Config
from retasc.models.rule import Rule
from retasc.utils import to_comma_separated
from retasc.yaml import yaml

logger = logging.getLogger(__name__)


class RuleParsingError(RuntimeError):
    pass


def iterate_yaml_files(path: str):
    if os.path.isdir(path):
        yield from chain.from_iterable(
            iglob(f"{path}/**/*.{suffix}", recursive=True) for suffix in ("yaml", "yml")
        )
    else:
        yield path


def parse_yaml_objects(rule_file: str) -> list[dict]:
    with open(rule_file) as file:
        data = yaml().load(file)
        if isinstance(data, list):
            return data
        return [data]


@dataclass
class ParseState:
    """Keeps state for parsing and validation."""

    config: Config
    rules: dict[str, Rule] = field(default_factory=dict)
    rule_files: defaultdict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    errors: list[str] = field(default_factory=list)

    def parse_rules(self, rule_file: str) -> None:
        logger.info("Parsing %s", rule_file)

        try:
            rule_data_list = parse_yaml_objects(rule_file)
        except YAMLError as e:
            self.errors.append(f"Invalid YAML file {rule_file!r}: {e}")
            return

        for rule_data in rule_data_list:
            try:
                rule = Rule(**rule_data)
            except ValidationError as e:
                self.errors.append(f"Invalid rule file {rule_file!r}: {e}")
                continue

            self.rule_files[rule.name].append(rule_file)
            self.rules[rule.name] = rule

    def validate_unique_rule_names(self) -> None:
        for name, files in self.rule_files.items():
            if len(files) > 1:
                file_list = to_comma_separated(files)
                self.errors.append(
                    f"Duplicate rule name {name!r} in files: {file_list})"
                )

    def validate_existing_dependent_rules(self) -> None:
        for rule in self.rules.values():
            errors = [
                error
                for prereq in rule.prerequisites
                for error in prereq.validation_errors(self.rules.values(), self.config)
            ]
            if errors:
                self._add_invalid_rule_error(rule, "\n  ".join(errors))

    def _add_invalid_rule_error(self, rule: Rule, error: str) -> None:
        filename = self.rule_files[rule.name][0]
        self.errors.append(
            f"Invalid rule {rule.name!r} (file {filename!r}):\n  {error}"
        )


def parse_rules(path: str, config: Config) -> dict[str, Rule]:
    """
    Parses rules in path recursively to dict with rule name as key and the rule
    as value.
    """
    state = ParseState(config=config)

    for rule_file in iterate_yaml_files(path):
        state.parse_rules(rule_file)

    state.validate_unique_rule_names()
    state.validate_existing_dependent_rules()

    if state.errors:
        error_list = "\n".join(state.errors)
        raise RuleParsingError(f"Failed to parse rules in {path!r}:\n{error_list}")

    if not state.rules:
        raise RuleParsingError(f"No rules found in {path!r}")

    return state.rules
