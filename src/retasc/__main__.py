#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import logging
import sys

from pydantic import ValidationError

from retasc import __doc__ as doc
from retasc import __version__
from retasc.retasc_logging import init_logging
from retasc.tracing import init_tracing
from retasc.validator.generate_schema import generate_schema
from retasc.validator.validate_rules import validate_rule

logger = logging.getLogger(__name__)


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

    if args.command == "validate-rule":
        try:
            validate_rule(args.rule_file)
            print("Validation succeeded: The rule file is valid")
        except ValidationError as e:
            print(f"Validation failed: The rule file is invalid: {e}")
            sys.exit(1)
    elif args.command == "generate-schema":
        generate_schema(args.schema_file, output_json=args.json)
    sys.exit(0)
