"""
`fpl tui` of 01.01.09-tui: the cell and the lines it leaves as plain
functions, the Textual application driven headless against a real
kernel (a snapshot of its screen after Shift-Enter), and the refusal in
a terminal that cannot draw.
"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from lit import env as lit_env
from lit import lit

HEADLESS = '''
import asyncio, html, os, re
from fpl.pty import attach
from fpl.tui import Tui

def screen(app):
    """The screen as text: the SVG export's text runs, placed by x."""
    svg = app.export_screenshot()
    rows = {}
    run = r'<text[^>]* x="([\\d.]+)" y="([\\d.]+)"[^>]*>(.*?)</text>'
    for m in re.finditer(run, svg):
        text = html.unescape(m[3]).replace("\\xa0", " ")
        rows.setdefault(float(m[2]), []).append((float(m[1]), text))
    out = []
    for y in sorted(rows):
        line = ""
        for x, text in sorted(rows[y]):
            line = line.ljust(round(x / 12.2)) + text
        out.append(line.rstrip())
    return "\\n".join(out)

async def main():
    conn = attach("h", os.environ)
    app = Tui(conn, "h", os.environ)
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.press(*"1 2 +")
        await pilot.press("shift+enter")
        await pilot.pause()
        print(screen(app))
        print("EDITOR", repr(app.query_one("#editor").text))
        await pilot.press("shift+enter")
        await pilot.press("ctrl+r")
        await pilot.pause()
        print("EDITOR", repr(app.query_one("#editor").text))
    conn.ask("stop")

asyncio.run(main())
'''


@pytest.fixture
def home() -> Generator[dict[str, str]]:
    """
    An environment with session files in a fresh short directory.
    """
    short = Path(tempfile.mkdtemp(prefix="fpl-tui-", dir="/tmp"))
    yield lit_env() | {
        "XDG_STATE_HOME": f"{short}/state",
        "XDG_CONFIG_HOME": f"{short}/config",
        "XDG_RUNTIME_DIR": f"{short}/run",
        "HOME": str(short),
    }
    shutil.rmtree(short, ignore_errors=True)


def test_the_cell_and_its_results_are_plain_functions() -> None:
    done = lit(
        "from fpl.tui import cell, evaluated\n"
        "lines = ['a', 'b', '|= 1', '|=', '', 'c', '|= 2']\n"
        "print(*(cell(lines, row) for row in (1, 3, 4, 5)))\n"
        "turn = [{'out': 'x\\n\\ny\\n'}]\n"
        "print(evaluated('\\n'.join(lines), 0, turn).split('\\n'))\n"
        "print(evaluated('q', 0, [{'out': ''}]) == 'q')\n"
        "print(evaluated('', 0, [{'out': 'z\\n'}]))\n"
    )
    assert done.returncode == 0, done.stderr.decode()
    got = done.stdout.decode().splitlines()
    assert got[0] == "(0, 2, 4) (0, 2, 4) None (5, 6, 7)"
    assert got[1] == "['a', 'b', '|= x', '|=', '|= y', '', 'c', '|= 2']"
    assert got[2] == "True"
    assert got[3] == "|= z"


def test_shift_enter_writes_the_result_under_the_cell(
    home: dict[str, str],
) -> None:
    pytest.importorskip("textual")
    done = subprocess.run(
        [sys.executable, "-c", HEADLESS],
        capture_output=True,
        text=True,
        env=home,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    shown = done.stdout
    assert "|= [ 1 2 + ]" in shown
    assert "trace: not yet" in shown
    assert "fuel" in shown
    editors = [x for x in shown.splitlines() if x.startswith("EDITOR")]
    assert editors == [
        "EDITOR '1 2 +\\n|= [ 1 2 + ]'",
        "EDITOR '1 2 +\\n|= [ 1 2 + ]'",
    ]


def test_a_terminal_that_cannot_draw_is_refused() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "fpl", "tui"],
        input="",
        capture_output=True,
        text=True,
        env=lit_env() | {"TERM": "dumb"},
        timeout=60,
        check=False,
    )
    assert done.returncode == 2
    assert "needs a terminal that can draw" in done.stderr
