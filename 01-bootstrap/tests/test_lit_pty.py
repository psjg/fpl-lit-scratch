"""
`fpl pty` of 01.01.08-pty, run as real processes: a named session is a
kernel that outlives each call, the transcript of a piped input is its
inputs with their results as `|=` lines, and a later call finds the log
the earlier one left.
"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from lit import env as lit_env


@pytest.fixture
def home() -> Generator[dict[str, str]]:
    """
    An environment whose session directory, log key and config lie in a
    fresh directory short enough for a socket path; the kernel it
    started is stopped afterwards.
    """
    short = Path(tempfile.mkdtemp(prefix="fpl-pty-", dir="/tmp"))
    env = lit_env() | {
        "XDG_STATE_HOME": f"{short}/state",
        "XDG_CONFIG_HOME": f"{short}/config",
        "XDG_RUNTIME_DIR": f"{short}/run",
        "HOME": str(short),
    }
    yield env
    subprocess.run(
        [sys.executable, "-m", "fpl", "pty", "--session", "t", "--stop"],
        env=env,
        check=False,
        timeout=30,
    )
    shutil.rmtree(short, ignore_errors=True)


def pty(
    env: dict[str, str], *args: str, stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    """
    `fpl pty --session t args` with stdin, text in and out.
    """
    return subprocess.run(
        [sys.executable, "-m", "fpl", "pty", "--session", "t", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )


def test_a_piped_input_comes_back_as_a_transcript(
    home: dict[str, str],
) -> None:
    done = pty(home, stdin="1 2 +\n")
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("1 2 +\n|= [ 1 2 + ]\n;; HEAD 1 $")


def test_the_next_call_joins_the_same_session(home: dict[str, str]) -> None:
    pty(home, stdin="1 2 +\n")
    second = pty(home, "--replay", stdin="3 4 +\nnope\n")
    assert second.returncode == 1, second.stderr
    heard = second.stdout
    assert heard.startswith("1 2 +\n|= [ 1 2 + ]\n3 4 +\n|= [ 3 4 + ]\n")
    assert "|= ERROR: 1:1 unknown word: nope" in heard
    again = pty(home, stdin=heard)
    assert again.returncode == 1
    assert "|= [ 1 2 + ]" in again.stdout


def test_stop_ends_the_kernel_and_a_bad_name_is_refused(
    home: dict[str, str],
) -> None:
    pty(home, stdin="1\n")
    assert pty(home, "--stop").returncode == 0
    refused = subprocess.run(
        [sys.executable, "-m", "fpl", "pty", "--session", "../x"],
        input="1\n",
        capture_output=True,
        text=True,
        env=home,
        timeout=60,
        check=False,
    )
    assert refused.returncode == 2
    assert "not a session name" in refused.stderr
