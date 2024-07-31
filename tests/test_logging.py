# SPDX-License-Identifier: GPL-3.0-or-later
import json
from unittest.mock import patch

from retasc.retasc_logging import DEFAULT_LOGGING_CONFIG, init_logging


def test_init_logging_with_default_config(monkeypatch):
    monkeypatch.setenv("RETASC_LOGGING_CONFIG", "")
    with patch("retasc.retasc_logging.logging.config") as mock:
        init_logging()
        mock.dictConfig.assert_called_once_with(DEFAULT_LOGGING_CONFIG)


def test_init_logging_with_custom_config(tmp_path, monkeypatch):
    config = {"version": 1}
    config_file = tmp_path / "logging.json"
    config_file.write_text(json.dumps(config))
    monkeypatch.setenv("RETASC_LOGGING_CONFIG", str(config_file))
    init_logging()
    with patch("retasc.retasc_logging.logging.config") as mock:
        init_logging()
        mock.dictConfig.assert_called_once_with(config)
