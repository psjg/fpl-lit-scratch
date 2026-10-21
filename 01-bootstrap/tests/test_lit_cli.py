"""
The `fpl` command line of 01.01.06-cli, run as a real process.

Bare `fpl` opens the interactive interface; `fpl <stage>` is one
filter; `fpl run <file>` runs the whole chain; `fpl graph` and
`fpl shell` show a composition. The command names come from the
registries (`fpl.pipe.PASSES`, `fpl.pipe.ENDS`, `fpl.run.COMPOSITIONS`),
so no stage name is spelled out in the CLI or in the tangler.
"""

import subprocess
import sys

from lit import env


def test_a_stage_main_exits_with_the_filter_status() -> None:
    """
    `python -m fpl.lex` handed no FON fails: exit 1, a stderr line.
    """
    done = subprocess.run(
        [sys.executable, "-m", "fpl.lex"],
        input=b"x",
        capture_output=True,
        env=env(),
        timeout=60,
        check=False,
    )
    assert done.returncode == 1
    assert done.stderr
