"""
# 01.01.09 Tui

`fpl tui --session NAME` is the web IDE's shape in a terminal, on the
kernel of the session NAME ([01.01.08-pty](01.01.08-pty.md), [the design
note](../../02-docs/02.05-project/notes/02.05.14-session-kernel.md)).
Textual is the library; it is the extra `tui`, and nothing else imports
it, so `fpl` starts without it.

On the left the editor, a plain text area. On the right the transcript
of the session, and under it the panes of the trace and the stepper,
stubs until the tracer of the playground has a terminal form. At the
bottom the status bar, and the keys: the session, its head, the fuel the
last turn spent against the budget, and its milliseconds.

The editor and the REPL are one session
([DI-0045](../../02-docs/02.05-project/inbox/DI-0045-editor-and-repl-session-collapse.md)):
**Shift-Enter** evaluates the cell under the cursor, the lines of the
text around it up to a blank line, and writes the results under it as
`|=` lines, replacing the results of an earlier evaluation
([DI-0044](../../02-docs/02.05-project/inbox/DI-0044-bqnpad-as-model-for-ide-repl.md)).
Many terminals cannot tell Shift-Enter from Enter, so **F5** and
**Alt-Enter** do the same. **Ctrl-R** reloads the transcript from the
log, **F6** moves between the panes, **Ctrl-Q** quits. There is no
mouse-only action.

The cell and the lines it leaves are plain functions, so they are tested
without a terminal; the application is driven headless in [the
test](../tests/test_lit_tui.py).

The full-screen interface of a session kernel.
"""

import sys
from collections.abc import Mapping
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, RichLog, Static, TextArea

from fpl.pty import Conn, attach, who

RESULT = "|="


def is_result(line: str) -> bool:
    """
    A line the kernel's transcript writes for a result.
    """
    return line == RESULT or line.startswith(RESULT + " ")


def cell(lines: list[str], row: int) -> tuple[int, int, int] | None:
    """
    The cell at `row`: the lines of its block up to a blank line, as
    (start, end, stop): the input is lines[start:end], the results of an
    earlier evaluation lines[end:stop]. None on a blank line.
    """
    if not lines[row].strip():
        return None
    start = row
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = start
    while end < len(lines) and lines[end].strip() and not is_result(lines[end]):
        end += 1
    stop = end
    while stop < len(lines) and is_result(lines[stop]):
        stop += 1
    return start, end, stop


def results(turns: list[dict[str, Any]]) -> list[str]:
    """
    The `|=` lines of what the turns printed.
    """
    return [
        f"{RESULT} {line}".rstrip()
        for turn in turns
        for line in turn["out"].splitlines()
    ]


def evaluated(text: str, row: int, turns: list[dict[str, Any]]) -> str:
    """
    The text with the results of `turns` under the cell at `row`,
    replacing the results that were there.
    """
    lines = text.split("\n")
    start, end, stop = cell(lines, row) or (row, row, row)
    lines[end:stop] = results(turns)
    return "\n".join(lines)


def status(name: str, head: int, fuel: int, turns: list[dict[str, Any]]) -> str:
    """
    The status bar: the session, its head, the fuel the turns spent
    against the budget, and their milliseconds.
    """
    spent = sum(t["spent"] or 0 for t in turns)
    ms = sum(t["ms"] for t in turns)
    return f" {name}  head {head}  fuel {spent}/{fuel}  {ms:.1f} ms"


class Tui(App[None]):
    """
    The editor, the transcript, the trace and stepper stubs, and the
    status bar, on one connection to a session kernel.
    """

    TITLE = "fpl"
    CSS = """
    #editor { width: 1fr; }
    #side { width: 1fr; }
    #transcript { height: 2fr; border: round $primary; }
    #trace, #stepper { height: 1fr; border: round $surface; }
    #status { height: 1; background: $primary; color: $text; }
    """
    BINDINGS = [
        Binding("shift+enter,f5,alt+enter", "evaluate", "Evaluate", priority=True),
        Binding("ctrl+r", "replay", "Reload"),
        Binding("f6", "app.focus_next", "Pane"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, conn: Conn, name: str, env: Mapping[str, str]) -> None:
        super().__init__()
        self.conn = conn
        self.session = name
        self.env = env

    def compose(self) -> ComposeResult:
        """
        The panes.
        """
        with Horizontal():
            yield TextArea(id="editor")
            with Vertical(id="side"):
                yield RichLog(id="transcript", wrap=True, markup=False)
                yield Static("trace: not yet", id="trace")
                yield Static("stepper: not yet", id="stepper")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        """
        Focus the editor and load the transcript.
        """
        self.query_one("#editor").focus()
        self.action_replay()

    def shown(self, text: str) -> None:
        """
        Write the transcript text into its pane.
        """
        self.query_one("#transcript", RichLog).write(text.rstrip("\n"))

    def action_replay(self) -> None:
        """
        Reload the transcript from the kernel's log.
        """
        pane = self.query_one("#transcript", RichLog)
        pane.clear()
        self.shown(self.conn.ask("replay")["transcript"])
        self.query_one("#status", Static).update(self.line([]))

    def line(self, turns: list[dict[str, Any]]) -> str:
        """
        The status bar for these turns, at the kernel's head.
        """
        hello = self.conn.ask("hello")
        return status(self.session, hello["head"], hello["fuel"], turns)

    def action_evaluate(self) -> None:
        """
        Feed the cell under the cursor to the kernel; its results go
        under it, and the whole of what happened into the transcript.
        """
        editor = self.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        lines = editor.text.split("\n")
        found = cell(lines, row)
        if found is None:
            self.query_one("#status", Static).update(" nothing to evaluate here")
            return
        source = "\n".join(lines[found[0] : found[1]]) + "\n"
        got = self.conn.ask("feed", text=source, who=who(self.env))
        editor.load_text(evaluated(editor.text, row, got["turns"]))
        editor.cursor_location = (row, col)
        self.shown(got["transcript"])
        self.query_one("#status", Static).update(self.line(got["turns"]))


def run(name: str, env: Mapping[str, str]) -> int:
    """
    Open the interface on the kernel of `name`, started if need be.
    Refused (status 2, one line on stderr): a session that cannot be
    attached.
    """
    try:
        conn = attach(name, env)
    except (OSError, ValueError, LookupError, TimeoutError) as error:
        print(f"fpl tui: {error}", file=sys.stderr)
        return 2
    Tui(conn, name, env).run()
    return 0
