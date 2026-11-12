"""Toets de fabula tegen het speedscope-bestand van dezelfde trace.

Gebruik: python3 -I test_tofabula.py TRACE.json X.speedscope.json X.fabula.json

Per run: het aantal stappen is de duur van ``· stappen``, de som van ``u``
de duur van ``· υ``; elke stap heeft ``src``; ops-rijen plus lege rijen is
``u``. Beide bestanden komen van hun eigen converter, dus de toets sluit
de lus tussen tospeedscope.py en tofabula.py.
"""

import json
import sys


def check(trace, scope, fab):
    """Geeft per run een regel; faalt op de eerste afwijking."""
    dur = {p["name"]: p["endValue"] - p["startValue"]
           for p in scope["profiles"]}
    out = []
    assert set(fab["runs"]) == {r["call"] for r in trace}
    for run in trace:
        call, steps = run["call"], fab["runs"][run["call"]]
        assert len(steps) == len(run["steps"]) == dur[f"{call} · stappen"]
        u = sum(s["u"] for s in steps)
        assert u == dur[f"{call} · υ"], (call, u)
        assert all(s["src"] for s in steps), call
        rows = sum(len(s["ops"]) if s["ops"] else s["u"] for s in steps)
        assert rows == u, (call, rows, u)
        for s, r in zip(steps, run["steps"]):
            assert s["ops"] is None or len(s["ops"]) == s["u"] == r["u"]
            lines = fab["files"][s["file"]]["lines"]
            assert s["src"] == lines[s["ln"] - 1]
        empty = sum(s["u"] for s in steps if s["ops"] is None)
        out.append(f"ok {call}: {len(steps)} stappen, {u} υ"
                   f" = {u - empty} ops + {empty} leeg")
    return out


def main():
    paths = sys.argv[1:4]
    trace, scope, fab = (json.load(open(p, encoding="utf-8")) for p in paths)
    for line in check(trace, scope, fab):
        print(line)
    print(f"geslaagd: {len(trace)} runs")


if __name__ == "__main__":
    main()
