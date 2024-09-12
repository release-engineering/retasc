#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import logging
import sys

from retasc import __doc__ as doc
from retasc import __version__
from retasc.models.generate_schema import generate_schema
from retasc.models.parse_rules import RuleParsingError, parse_rules
from retasc.retasc_logging import init_logging
from retasc.run import run
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

    subparsers.add_parser(
        "run", help="Process rules, data from Product Pages and apply changes to Jira"
    )
    subparsers.add_parser(
        "dry-run",
        help='Same as "run" but without creating, deleting or modifying any Jira issues',
    )

    return parser.parse_args()


def main():
    args = parse_args()
    init_logging()
    init_tracing()

    if args.command == "validate-rules":
        try:
            parse_rules(args.rule_file)
        except RuleParsingError as e:
            print(f"Validation failed: {e}")
            sys.exit(1)
        print("Validation succeeded: The rule files are valid")
    elif args.command == "generate-schema":
        generate_schema(args.schema_file, output_json=args.json)
    elif args.command in ("run", "dry-run"):
        dry_run = args.command == "dry-run"
        run(dry_run=dry_run)
    sys.exit(0)
