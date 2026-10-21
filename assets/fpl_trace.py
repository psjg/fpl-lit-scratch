"""
Reduction trace for the playground stepper: one frame per evaluator step.

Runs under Pyodide beside the walker (it imports only `fpl`). It mirrors
`fpl.evaluate.final` one step at a time instead of calling it, so a run
that the stepper shows is the run the evaluator takes: same `step`, same
fuel rule, one frame per fuel unit. The walker stays untouched; the hook
that would replace this copy is the design note's first open item.
"""

import json

from fpl.ast_core import Call, Define, Run
from fpl.desugar import desugar, listing
from fpl.errors import FplError
from fpl.evaluate import State, effect_line, step
from fpl.lex import lex
from fpl.parse import parse
from fpl.print import render

FRAMES = 2000
"""The most frames recorded per run line; the run is cut there, not failed."""
FUEL = 100_000
"""The steps a traced run line may take, as in a plain run."""


def shown(stack) -> str:
    """The stack as the printer writes one line, for display."""
    return render(listing((stack,))).strip()


def label(node) -> str:
    """What the step is about: a word's name, else the node's kind."""
    return node.name if isinstance(node, Call) else type(node).__name__.lower()


def lines(source: str) -> list[dict]:
    """
    Each run line of `source` as {line, frames, end, error}; a frame is
    {n, node, line, col, stack, waiting}. `end` is "done", "error" or
    "cut" (FRAMES reached); `error` is the refusal text, if any.
    """
    statements = desugar(parse(lex(source)))
    words = {s.word: s.code for s in statements if isinstance(s, Define)}
    runs = []
    for s in statements:
        if not isinstance(s, Run):
            continue
        stack, waiting = (), list(reversed(s.code))
        frames = [{"n": 0, "node": "start", "stack": shown(stack),
                   "waiting": len(waiting), "line": s.span.line, "col": s.span.col}]
        end, error = "done", ""
        try:
            while waiting:
                if len(frames) > FRAMES:
                    end = "cut"
                    break
                if len(frames) > FUEL:
                    raise FplError(s.span, "out of fuel")
                node = waiting.pop()
                after = step(State(stack, (node,), words))
                stack = after.stack
                waiting.extend(reversed(after.code))
                span = getattr(node, "span", None)
                frames.append({
                    "n": len(frames), "node": label(node), "stack": shown(stack),
                    "waiting": len(waiting),
                    "line": span.line if span else s.span.line,
                    "col": span.col if span else s.span.col,
                })
        except FplError as e:
            end, error = "error", str(e)
        except RecursionError:
            end, error = "error", "recursion too deep"
        runs.append({"line": s.span.line, "frames": frames, "end": end, "error": error})
    return runs


def trace(source: str) -> str:
    """JSON for the stepper; a parse or check failure is {"error": text}."""
    try:
        return json.dumps({"runs": lines(source)})
    except Exception as e:  # noqa: BLE001 - any front-end failure is shown, not raised
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
