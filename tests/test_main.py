# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from runpy import run_module
from unittest.mock import patch, MagicMock

from pytest import mark, raises


def run_main(*args, code=None):
    with patch.object(sys, "argv", ["retasc", *args]):
        if code is None:
            run_module("retasc")
            return

        with raises(SystemExit) as e:
            run_module("retasc")

        assert e.value.code == code


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

def test_validate_rule_called(tmp_path):
    rule_file = "mock"
    with patch("retasc.validator.validate_rules.validate_rule", MagicMock(return_value=True)) as mock_validate_rule:
        run_main("--validate-rule", str(rule_file), code=None)
        mock_validate_rule.assert_called_once_with(str(rule_file))
