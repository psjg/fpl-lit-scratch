"""
Chrome trace-event JSON of one run of the tangled walker (the one the
playground ships), for Perfetto (ui.perfetto.dev) or chrome://tracing: a
slice per pass (lex, parse, desugar, elaborate, evaluate, print), a
slice per run line, an instant per call of a defined word and a counter
of the fuel spent. The walker is not edited: while a run is traced,
`step` of fpl.evaluate is wrapped; untraced runs are the walker as is.
"""

import json
import sys
import time
from collections.abc import Callable
from typing import Any

FUEL = 1_000_000
"""Steps a run line may take, as the walker's run gives."""

LIMIT = 200_000
"""Events kept at most; calls beyond it are counted, not recorded."""

type Event = dict[str, Any]
type Result = tuple[str, list[Event], str | None]


class Clock:
    """Microseconds since creation, from the monotonic clock."""

    def __init__(self) -> None:
        self.t0 = time.perf_counter_ns()

    def __call__(self) -> float:
        return (time.perf_counter_ns() - self.t0) / 1000


def span_(name: str, cat: str, ts: float, end: float, **args: Any) -> Event:
    """A complete ('X') event from ts to end, in microseconds."""
    return {
        "name": name, "cat": cat, "ph": "X", "ts": ts,
        "dur": max(end - ts, 0.0), "pid": 1, "tid": 1, "args": args,
    }  # fmt: skip


def traced(source: str, fuel: int | None = FUEL) -> tuple[str, str]:
    """
    Runs the program as `driver.run` does and returns its output and
    the trace as Chrome trace-event JSON text. A refusal loses the
    events here; `traced_events` keeps both.
    """
    out, events, failure = traced_events(source, fuel)
    doc = {"traceEvents": events, "displayTimeUnit": "ms",
           "otherData": {"failure": failure}}  # fmt: skip
    return out, json.dumps(doc)


class Recorder:
    """
    Collects the events of one run; its `observe` is the step observer.
    """

    def __init__(self, limit: int = LIMIT, fuel: int | None = FUEL) -> None:
        self.limit = limit
        self.fuel = fuel
        self.clock = Clock()
        self.dropped = 0
        self.meter: Any = None
        self.start = 0.0
        self.calls = 0
        self.events: list[Event] = [
            {"name": "process_name", "ph": "M", "pid": 1,
             "args": {"name": "fpl"}},
            {"name": "thread_name", "ph": "M", "pid": 1, "tid": 1,
             "args": {"name": "walker"}},
        ]  # fmt: skip

    def spent(self, meter: Any) -> int | None:
        """Steps the meter has charged, None when unbounded."""
        if self.fuel is None or meter.left is None:
            return None
        return self.fuel - meter.left

    def close(self) -> None:
        """Ends the slice of the run line in progress, if any."""
        if self.meter is not None:
            name = f"line {self.meter.span.line}"
            self.events.append(
                span_(name, "run", self.start, self.clock(),
                       fuel=self.spent(self.meter), calls=self.calls)
            )  # fmt: skip

    def observe(self, node: Any, words: Any, meter: Any) -> None:
        """A step about to run: a new line, or a call of a word."""
        now = self.clock()
        if meter is not self.meter:
            self.close()
            self.meter, self.start, self.calls = meter, now, 0
        if not (type(node).__name__ == "Call" and node.name in words):
            return
        self.calls += 1
        if len(self.events) >= self.limit:
            self.dropped += 1
            return
        spent = self.spent(meter)
        self.events.append({"name": node.name, "cat": "call", "ph": "i",
                            "s": "t", "ts": now, "pid": 1, "tid": 1,
                            "args": {"fuel": spent}})  # fmt: skip
        self.events.append({"name": "fuel", "ph": "C", "ts": now,
                            "pid": 1, "args": {"spent": spent}})  # fmt: skip

    def phase[T](self, name: str, work: Callable[[], T]) -> T:
        """Runs work as the pass `name`, timed even if it refuses."""
        start = self.clock()
        try:
            return work()
        finally:
            self.events.append(span_(name, "pass", start, self.clock()))


def traced_events(
    source: str, fuel: int | None = FUEL, limit: int = LIMIT
) -> Result:
    """
    Output, events and the refusal's message (None when all went well).
    """
    walk = sys.modules["fpl.evaluate"]
    run = sys.modules["fpl.run"]
    errors = sys.modules["fpl.errors"]
    rec = Recorder(limit, fuel)
    plain = walk.step

    def step(state: Any) -> Any:
        rec.observe(state.code[0], state.words, walk.FUEL.get())
        return plain(state)

    out, failure = "", None
    try:
        src = run._notebook_indent(source)
        tokens = rec.phase("lex", lambda: run.lex(src))
        tree = rec.phase("parse", lambda: run.parse(tokens))
        stmts = rec.phase("desugar", lambda: run.desugar(tree))
        stmts = rec.phase("elaborate", lambda: run.elaborate(stmts))
        walk.step = step
        try:
            results = rec.phase(
                "evaluate", lambda: walk._eval_fn(stmts, fuel)
            )
        finally:
            walk.step = plain
            rec.close()
        out = rec.phase("print", lambda: run.render(run.listing(results)))
    except errors.FplError as e:
        failure = str(e)
    if rec.dropped:
        rec.events.append({"name": "calls dropped", "ph": "i", "s": "g",
                           "ts": rec.clock(), "pid": 1, "tid": 1,
                           "args": {"n": rec.dropped}})  # fmt: skip
    return out, rec.events, failure
