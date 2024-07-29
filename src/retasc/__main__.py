#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import sys

from retasc import __doc__ as doc
from retasc import __version__
from retasc.retasc_logging import init_logging
from retasc.tracing import init_tracing
from retasc.validator.generate_schema import generate_schema
from retasc.validator.validate_rules import validate_rule


def parse_args():
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate-rule", help="Validate a rule file"
    )
    validate_parser.add_argument(
        "rule_file", type=str, help="Path to the rule file to validate"
    )

    generate_parser = subparsers.add_parser("generate-schema", help="Generate a schema")
    generate_parser.add_argument(
        "schema_file", type=str, help="Output schema file to generate"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    init_logging()
    init_tracing()

    try:
        if args.command == "validate-rule":
            validate_rule(args.rule_file)
        elif args.command == "generate-schema":
            generate_schema(args.schema_file)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
