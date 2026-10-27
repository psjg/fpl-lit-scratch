"""
The playground's reduction recorder (assets/fpl_steprec.py) runs under
Pyodide beside the tangled walker (01-bootstrap/python/fpl), not this
package, so it is checked in a child interpreter with that walker on
the path.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def traced(source: str) -> dict[str, Any]:
    code = "import fpl_steprec, sys; print(fpl_steprec.trace(sys.argv[1]))"
    env_path = f"{ROOT / '01-bootstrap' / 'python'}:{ROOT / 'assets'}"
    out = subprocess.run(
        [sys.executable, "-P", "-c", code, source],
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": env_path},
    )
    assert out.returncode == 0, out.stderr
    result: dict[str, Any] = json.loads(out.stdout)
    return result


def test_one_frame_per_step_and_the_final_stack() -> None:
    run: dict[str, Any] = traced("inc : n -- n\n\t1 +\n1 inc inc\n")["runs"][0]
    assert [f["n"] for f in run["frames"]] == list(range(8))
    assert run["frames"][-1]["stack"] == "3"
    assert run["end"] == "done"


def test_a_word_body_step_points_into_the_body() -> None:
    source = "inc : n -- n\n\t1 +\n1 inc\n"
    frames: list[dict[str, Any]] = traced(source)["runs"][0]["frames"]
    assert any(f["node"] == "+" and f["line"] == 2 for f in frames)


def test_a_loop_is_cut_not_failed() -> None:
    run: dict[str, Any] = traced("f : --\n\tf\nf\n")["runs"][0]
    assert run["end"] == "cut"
    assert len(run["frames"]) > 1000


def test_a_front_end_failure_is_reported() -> None:
    assert "unknown word" in traced("1 bogus\n")["error"]


def test_playground_python_modules_have_distinct_names() -> None:
    """
    The stepper recorder (assets/) and Perfetto tracer (.wasm/) share
    one Pyodide `sys.modules`; a shared name shadows one of them.
    """
    assets = {p.stem for p in (ROOT / "assets").glob("*.py")}
    wasm = {p.stem for p in (ROOT / ".wasm").glob("*.py")}
    assert assets.isdisjoint(wasm), assets & wasm
    assert "fpl_trace" in wasm
    assert "fpl_steprec" in assets


def test_python_imports_in_playground_js_name_shipped_modules() -> None:
    """
    Each `import fpl_x` inside assets/*.js names a shipped module.
    """
    shipped = {p.stem for p in (ROOT / "assets").glob("*.py")} | {
        p.stem for p in (ROOT / ".wasm").glob("*.py")
    }
    for js in (ROOT / "assets").glob("*.js"):
        for name in re.findall(r"import (fpl_\w+)", js.read_text()):
            assert name in shipped, (js.name, name)
