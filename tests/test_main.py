# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from runpy import run_module
from unittest.mock import patch

from pytest import mark, raises


def run_main(*args, code=None):
    with patch.object(sys, "argv", ["retasc", *args]):
        if code is None:
            run_module("retasc")
            return

        with raises(SystemExit) as e:
            run_module("retasc")
            assert e.code == code


@mark.parametrize("arg", ("--help", "-h"))
def test_help(arg, capsys):
    run_main(arg, code=0)
    stdout, _ = capsys.readouterr()
    assert "ReTaSC" in stdout
    assert "--help" in stdout
    assert "-h" in stdout
    assert "--version" in stdout
    assert "-v" in stdout


@mark.parametrize("arg", ("--version", "-v"))
def test_version(arg, capsys):
    run_main(arg, code=0)
    stdout, _ = capsys.readouterr()
    assert "retasc" in stdout


def test_dummy_run(capsys):
    run_main()
    stdout, stderr = capsys.readouterr()
    assert stdout == ""
    assert stderr == ""
