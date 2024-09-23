# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from glob import iglob
from itertools import chain

import yaml
from pydantic import ValidationError

from retasc.validator.models import Rule

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
        data = yaml.safe_load(file)
        if isinstance(data, list):
            return data
        return [data]


def template_filenames(rule: Rule) -> Iterator[str]:
    for issue in rule.jira_issues:
        yield issue.template
        yield from (x.template for x in issue.subtasks)


def template_paths(rule: Rule, templates_path: str) -> Iterator[str]:
    for file in template_filenames(rule):
        yield f"{templates_path}/{file}"


def to_comma_separated(items: list) -> str:
    return ", ".join(sorted(repr(str(x)) for x in items))


@dataclass
class ParseState:
    """Keeps state for parsing and validation."""

    rules: dict[str, Rule] = field(default_factory=dict)
    rule_files: defaultdict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    errors: list[str] = field(default_factory=list)

    def parse_rules(self, rule_file: str) -> None:
        logger.info("Parsing %s", rule_file)

        try:
            rule_data_list = parse_yaml_objects(rule_file)
        except yaml.YAMLError as e:
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
            missing_rules = [
                name
                for name in rule.prerequisites.dependent_rules
                if name not in self.rules
            ]
            if missing_rules:
                rules_list = to_comma_separated(missing_rules)
                self._add_invalid_rule_error(
                    rule, f"Dependent rules do not exist: {rules_list}"
                )

    def validate_existing_jira_templates(self, templates_path: str) -> None:
        for rule in self.rules.values():
            missing_files = [
                file
                for file in template_paths(rule, templates_path)
                if not os.path.isfile(file)
            ]
            if missing_files:
                file_list = to_comma_separated(missing_files)
                self._add_invalid_rule_error(
                    rule,
                    f"Jira issue template files not found: {file_list}",
                )

    def _add_invalid_rule_error(self, rule: Rule, error: str) -> None:
        filename = self.rule_files[rule.name][0]
        self.errors.append(f"Invalid rule {rule.name!r} (file {filename!r}): {error}")


def parse_rules(path: str, templates_path: str = ".") -> dict[str, Rule]:
    """
    Parses rules in path recursively to dict with rule name as key and the rule
    as value.
    """
    state = ParseState()

    for rule_file in iterate_yaml_files(path):
        state.parse_rules(rule_file)

    state.validate_unique_rule_names()
    state.validate_existing_dependent_rules()
    state.validate_existing_jira_templates(templates_path)

    if state.errors:
        error_list = "\n".join(state.errors)
        raise RuleParsingError(f"Failed to parse rules in {path!r}:\n{error_list}")

    if not state.rules:
        raise RuleParsingError(f"No rules found in {path!r}")

    return state.rules
