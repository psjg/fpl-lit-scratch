"""
The installed `fpl` command: declared dependency, script entry, help.
"""

import tomllib

from lit import BOOTSTRAP, lit

PROJECT = tomllib.loads((BOOTSTRAP / "pyproject.toml").read_text())


def test_click_is_a_declared_dependency() -> None:
    """
    The CLI imports Click, so the project must declare it.
    """
    names = {
        d.split(">")[0].split("=")[0].strip().lower()
        for d in PROJECT["project"]["dependencies"]
    }
    assert "click" in names


def test_the_script_entry_points_at_a_callable_that_lists_commands() -> None:
    """
    The `fpl` script entry resolves, and calling it lists commands.
    """
    target = PROJECT["project"]["scripts"]["fpl"]
    module, _, attr = target.partition(":")
    result = lit(
        f"import sys; from {module} import {attr} as e; "
        "sys.argv = ['fpl', '--help']; sys.exit(e())"
    )
    out = result.stdout.decode()
    assert result.returncode == 0, result.stderr.decode()
    for command in ("run", "lex", "parse", "eval"):
        assert command in out


def test_importing_fpl_does_not_import_click() -> None:
    """
    The website imports `fpl` where Click is absent.
    """
    result = lit(
        "import sys; import fpl; import fpl.run; "
        "sys.exit('click' in sys.modules)"
    )
    assert result.returncode == 0, result.stderr.decode()
