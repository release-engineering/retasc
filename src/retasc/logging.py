# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging.config
import os

DEFAULT_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "retasc": {
            "level": "DEBUG",
        },
        # Skip printing tracebacks on frequent tracing connection issues
        "opentelemetry.sdk.trace.export": {
            "level": "CRITICAL",
        },
    },
    "handlers": {
        "console": {
            "formatter": "bare",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "DEBUG",
        },
    },
    "formatters": {
        "bare": {
            "format": "[%(asctime)s] [%(process)d] [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def init_logging():
    config = DEFAULT_LOGGING_CONFIG

    path = os.getenv("RETASC_LOGGING_CONFIG")
    if path:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)

    logging.config.dictConfig(config)
