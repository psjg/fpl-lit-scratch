"""
Overhead of tracing the tangled walker: best of N wall times of the same
program untraced (`run.default.src`) and under fpl_trace.traced.
From .wasm/:  PYTHONPATH=../01-bootstrap/python:. python bench_trace.py [N]
"""

import sys
import time

import fpl.evaluate
import fpl.run as run
import fpl_trace

SRC = (
    "dbl : n -- n\n\tdup +\n\n"
    "inc : n -- n\n\t1 +\n\n"
    + "1 [dbl inc dbl inc] 20 repeat\n" * 100
)


def best(n: int, call) -> float:
    times = []
    for _ in range(n):
        t = time.perf_counter()
        call(SRC)
        times.append(time.perf_counter() - t)
    return min(times)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    off = best(n, run.default.src)
    on = best(n, fpl_trace.traced)
    events = len(fpl_trace.traced_events(SRC)[1])
    print(f"off {off * 1e3:.1f} ms  on {on * 1e3:.1f} ms  x{on / off:.2f}  events {events}")
