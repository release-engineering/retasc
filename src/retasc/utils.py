# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Iterable


def to_comma_separated(items: Iterable) -> str:
    return ", ".join(sorted(repr(str(x)) for x in items))
