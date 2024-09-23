#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import logging
import sys

from retasc import __doc__ as doc
from retasc import __version__
from retasc.retasc_logging import init_logging
from retasc.tracing import init_tracing
from retasc.validator.generate_schema import generate_schema
from retasc.validator.parse_rules import RuleParsingError, parse_rules

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
    sys.exit(0)
