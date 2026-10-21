"""
The tangled tree, `python/fpl`, is what the notes say, and it runs.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from lit import TANGLE, TIMEOUT, fpl, lit


def tangle(*args: str) -> subprocess.CompletedProcess[str]:
    """
    Run tangle.py with `args`; it never writes into the repository here.
    """
    return subprocess.run(
        [sys.executable, str(TANGLE), *args],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


def test_the_committed_tangle_is_current() -> None:
    """
    `tangle.py --check` finds nothing stale: every note was retangled.
    """
    result = tangle("--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_out_writes_the_package_into_another_directory(
    tmp_path: Path,
) -> None:
    """
    `--out DIR` tangles into DIR/fpl and leaves python/ alone.
    """
    result = tangle("--out", str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "fpl" / "arrow.py").is_file()
    assert (tmp_path / "fpl" / "__main__.py").is_file()


def test_a_stage_reads_what_source_wrote() -> None:
    """
    `fpl source | fpl lex` runs, and `fpl source | fpl render` gives the
    text back.
    """
    text = b"1 2 +\n"
    source = fpl("source", stdin=text)
    assert source.returncode == 0, source.stderr
    lexed = fpl("lex", stdin=source.stdout)
    assert lexed.returncode == 0, lexed.stderr
    assert lexed.stdout
    rendered = fpl("render", stdin=source.stdout)
    assert (rendered.returncode, rendered.stdout) == (0, text)


def test_help_names_run_and_every_stage() -> None:
    """
    The command line lives in fpl.cli now; `fpl --help` still lists run
    and the seven stages.
    """
    result = fpl("--help")
    assert result.returncode == 0, result.stderr
    listed = result.stdout.decode().split("Commands:")[1].split()
    stages = ("desugar", "elaborate", "eval", "lex", "parse", "render")
    assert set(stages) | {"run", "source"} <= set(listed)


def test_importing_fpl_leaves_click_out() -> None:
    """
    The website imports fpl in Pyodide, where click is absent; only the
    command line may import it.
    """
    result = lit("import sys, fpl; print('click' in sys.modules)")
    assert (result.returncode, result.stdout) == (0, b"False\n")


def test_the_codec_and_graph_notes_tangle_to_modules() -> None:
    """
    01.01.05-codec and 01.04.05-graph are registered, so fpl.codec and
    fpl.graph import.
    """
    result = lit("import fpl.codec, fpl.graph")
    assert result.returncode == 0, result.stderr


def load_tangle() -> ModuleType:
    """
    tangle.py as a module, so a test can point it at a copy of python/.
    """
    spec = importlib.util.spec_from_file_location("tangle", TANGLE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_names_each_file_that_differs_or_is_missing(
    tmp_path: Path,
) -> None:
    """
    A prose edit with no retangle shows as a stale file, one that is
    missing or has no note shows too, and a current copy shows nothing.
    """
    tangle_py = load_tangle()
    copy = tmp_path / "fpl"
    shutil.copytree(
        tangle_py.OUT, copy, ignore=shutil.ignore_patterns("__pycache__")
    )
    assert tangle_py.stale(copy) == []
    (copy / "arrow.py").write_text("# edited by hand\n")
    (copy / "codec.py").unlink()
    (copy / "orphan.py").write_text("")
    named = sorted(path.name for path in tangle_py.stale(copy))
    assert named == ["arrow.py", "codec.py", "orphan.py"]
