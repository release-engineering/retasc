# SPDX-License-Identifier: GPL-3.0-or-later
import importlib
import pkgutil

from jinja2 import Environment


def update_environment(env: Environment):
    """
    Load all extension sub-modules which update the environment for
    templating.
    """
    for module_info in pkgutil.walk_packages(path=__path__, prefix=f"{__name__}."):
        module = importlib.import_module(module_info.name)
        module.update_environment(env)
