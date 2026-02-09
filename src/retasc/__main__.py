#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import json
import logging
import os
import sys

from retasc import __doc__ as doc
from retasc import __version__
from retasc.models.config import Config, parse_config
from retasc.models.generate_schema import generate_schema
from retasc.models.parse_rules import RuleParsingError, parse_rules
from retasc.retasc_logging import init_logging
from retasc.run import dry_run, run
from retasc.tracing import init_tracing

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate-rules", help="Validate a rule file"
    )
    validate_parser.add_argument(
        "rule_file", type=str, help="Path to the rule file or directory to validate"
    )

    generate_parser = subparsers.add_parser(
        "generate-schema", help="Generate YAML or JSON schema"
    )
    generate_parser.add_argument(
        "schema_file",
        type=str,
        nargs="?",
        help="Output schema YAML or JSON file to generate (default is stdout)",
    )
    generate_parser.add_argument(
        "-j",
        "--json",
        help="Generate JSON instead of the default YAML",
        action="store_true",
    )
    generate_parser.add_argument(
        "-c",
        "--config",
        help="Generate schema for the configuration instead of rules",
        action="store_true",
    )

    run_parser = subparsers.add_parser(
        "run", help="Process rules, data from Product Pages and apply changes to Jira"
    )
    dry_run_parser = subparsers.add_parser(
        "dry-run",
        help='Same as "run" but without creating, deleting or modifying any Jira issues',
    )
    for subparser in run_parser, dry_run_parser:
        subparser.add_argument(
            "--report",
            type=str,
            help="Output path for the report JSON file",
        )
        subparser.add_argument(
            "rule_files",
            metavar="RULE_FILE",
            type=str,
            nargs="*",
            help="Path to rule files or directories (default is from the config file)",
        )

    return parser.parse_args()


def get_config() -> Config:
    config_path = os.environ["RETASC_CONFIG"]
    return parse_config(config_path)


def _validate_rules(rule_file):
    config = get_config()
    try:
        parse_rules(rule_file, config=config)
    except RuleParsingError as e:
        print(f"Validation failed: {e}")
        sys.exit(1)
    print("Validation succeeded: The rule files are valid")


def to_json_serializable(obj):
    try:
        return json.JSONEncoder().default(obj)
    except TypeError:
        return str(obj)


def _run(args):
    jira_token = os.environ.get("RETASC_JIRA_TOKEN")
    jira_password = os.environ.get("RETASC_JIRA_PASSWORD")
    jira_username = os.environ.get("RETASC_JIRA_USERNAME")
    config = get_config()
    run_fn = run if args.command == "run" else dry_run
    rule_files = args.rule_files or [config.rules_path]
    report = run_fn(
        config=config,
        rule_files=rule_files,
        jira_token=jira_token,
        jira_username=jira_username,
        jira_password=jira_password,
    )

    if args.report:
        with open(args.report, "w") as f:
            json.dump(report.data, f, indent=2, default=to_json_serializable)

    if report.errors:
        errors = "\n".join(report.errors)
        raise SystemExit(f"❌ Errors:\n{errors}")


def main():
    args = parse_args()
    init_logging()
    init_tracing()

    if args.command == "validate-rules":
        _validate_rules(args.rule_file)
    elif args.command == "generate-schema":
        generate_schema(args.schema_file, output_json=args.json, config=args.config)
    elif args.command in ("run", "dry-run"):
        _run(args)

    sys.exit(0)
