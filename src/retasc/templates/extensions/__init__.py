# SPDX-License-Identifier: GPL-3.0-or-later
import importlib
import importlib.util
import logging
import pkgutil
from pathlib import Path

from jinja2 import Environment

logger = logging.getLogger(__name__)


class TemplateExtensionLoader:
    last_extension_index = 0

    def load(self, path: Path, env: Environment) -> None:
        self.last_extension_index += 1
        name = f"retasc.templates.extensions.ext{self.last_extension_index}.{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec) if spec else None

        if spec is None or spec.loader is None or module is None:
            raise RuntimeError(f"Could not load extensions from {path}")

        spec.loader.exec_module(module)
        logging.info("Loading template extension: %s", path)
        module.update_environment(env)


def update_environment(env: Environment):
    """
    Call update_environment(env) for built-in extensions sub-modules.
    """
    for module_info in pkgutil.walk_packages(path=__path__, prefix=f"{__name__}."):
        module = importlib.import_module(module_info.name)
        module.update_environment(env)


def update_environment_in_paths(paths: list[Path], env: Environment):
    """
    Call update_environment(env) in sub-modules and directories.
    """
    loader = TemplateExtensionLoader()
    for path in paths:
        if path.is_dir():
            for file in path.glob("*.py"):
                loader.load(file, env)
        else:
            loader.load(path, env)
