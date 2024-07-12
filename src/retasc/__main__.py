#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse

from retasc import __doc__ as doc
from retasc import __version__
from retasc.retasc_logging import init_logging
from retasc.tracing import init_tracing


def parse_args():
    parser = argparse.ArgumentParser(description=doc)
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser.parse_args()


parse_args()
init_logging()
init_tracing()
