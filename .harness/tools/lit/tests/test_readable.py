"""readable: facts from asserts, safe answers, scoring, the CLI."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from lit import readable, web
from support import GOOD, lit, md, page

SRC = '''
import pytest
from demo import add


def says(x: int) -> int:
    """Doubles x.

    A second paragraph that is not quoted.
    """
    return x * 2


def silent(x: int) -> int:
    return x


class Holder:
    pass


def test_plain() -> None:
    assert add(1, 2) == 3
    assert add(1, 2) is None
    assert add(1, 2) != 3
    assert add(1, 2) is not None
    assert add(1, 2) < 3


def test_local() -> None:
    x = add(1, 2)
    assert x == 3
    assert add(x, 1) == 4


def test_helpers() -> None:
    assert says(2) == 4
    assert silent(2) == 2
    assert unknown(1) == 2


@pytest.mark.parametrize("a, b", [(1, 2), (3, 4), (5,), 7])
def test_string(a: int, b: int) -> None:
    assert add(a, 1) == b


@pytest.mark.parametrize(("a", "b"), [(1, 2)])
@pytest.mark.parametrize(["c"], [5, 6])
@pytest.mark.skip
@pytest.mark.parametrize(c_names, [(1,)])
def test_product(a: int, b: int, c: int) -> None:
    assert add(a, c) == b


@pytest.mark.parametrize("n", [1, 2])
def test_single(n: int) -> None:
    assert add(n, n) == n * 2


@pytest.mark.parametrize("n", rows())
def test_dynamic(n: int) -> None:
    assert add(n, n) == 2
'''


def questions() -> list[str]:
    """Each fact of SRC as ``question = answer``, for a page of add."""
    items = readable.facts("t.py", SRC, {"add"})
    return [f"{f.question} = {f.expected}" for f in items]


def test_facts_from_plain_asserts() -> None:
    """== and is None become facts; other asserts do not."""
    got = [q for q in questions() if q.startswith("What is `add(1, 2)`?")]
    assert got == [
        "What is `add(1, 2)`? = 3",
        "What is `add(1, 2)`? = None",
    ]


def test_facts_drop_locals() -> None:
    """A fact over a test's local variable is dropped."""
    assert not [q for q in questions() if "add(x, 1)" in q]


def test_facts_quote_documented_helpers_only() -> None:
    """A helper with a docstring is quoted; one without is dropped."""
    got = questions()
    assert "What is `says(2)`? Here `says` is: Doubles x. = 4" in got
    assert not [q for q in got if "silent" in q or "unknown" in q]


def test_facts_from_string_parametrize_drop_bad_rows() -> None:
    """Rows of the wrong shape are dropped from a table."""
    got = questions()
    assert "What is `add(1, 1)`? = 2" in got
    assert "What is `add(3, 1)`? = 4" in got
    assert not [q for q in got if "add(5, 1)" in q or "add(7, 1)" in q]


def test_facts_from_tuple_names_and_two_decorators() -> None:
    """Two tables multiply; argnames may be a tuple or a list."""
    got = questions()
    assert "What is `add(1, 5)`? = 2" in got
    assert "What is `add(1, 6)`? = 2" in got


def test_facts_from_single_parameter() -> None:
    """One parameter's rows are single values; an expected value that
    is no literal (``1 * 2``) cannot be judged, so its fact goes."""
    got = questions()
    assert not [q for q in got if q.endswith("* 2")]


def test_prompt_numbers_the_questions() -> None:
    """The prompt holds the chapter and the numbered questions."""
    items = [readable.Fact("t.py:1", "What is `x`?", "1")]
    got = readable.prompt("chapter text", items)
    assert "chapter text" in got
    assert "1. What is `x`?" in got


@dataclass(frozen=True)
class Point:
    """A page type, for answers."""

    x: int
    y: int = 0


@dataclass(frozen=True)
class Checked:
    """A record that runs code of its own when built."""

    x: int

    def __post_init__(self) -> None:
        """Code a model's answer must not run."""


class Plain:
    """A class that is no record at all."""


SPACE: dict[str, object] = {
    "Point": Point,
    "Checked": Checked,
    "Plain": Plain,
    "k": 3,
}


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("3", 3),
        ("-3", -3),
        ("'a'", "a"),
        ("(1, [2], {3: 4}, {5})", (1, [2], {3: 4}, {5})),
        ("Point(1, y=2)", Point(1, 2)),
        ("None", None),
    ],
)
def test_value_evaluates_safe_answers(text: str, want: object) -> None:
    """Literals, containers and the page's types are evaluated."""
    assert readable.value(text, SPACE) == want


@pytest.mark.parametrize(
    "text",
    [
        "k",
        "Point(1).x",
        "len([])",
        "1(2)",
        "Point(1)(2)",
        "1 + 2",
        "Checked(1)",
        "Plain()",
    ],
)
def test_value_refuses_unsafe_answers(text: str) -> None:
    """Names outside the records, attributes, calls of anything but a
    record, and records with code of their own are refused."""
    with pytest.raises(ValueError, match=r"."):
        readable.value(text, SPACE)


def test_same_compares_values() -> None:
    """An answer is right when it evaluates to the expected value."""
    assert readable.same("Point(1, 2)", "Point(1, y=2)", SPACE)
    assert not readable.same("1", "2", SPACE)


def test_same_reads_a_bare_message_as_a_string() -> None:
    """An unquoted answer equals an expected string by its text."""
    assert readable.same("'boom now'", "boom now", SPACE)
    assert readable.same("'?'", " ? ", SPACE)
    assert not readable.same("'boom'", "bang", SPACE)
    assert not readable.same("3", "three", SPACE)
    assert not readable.same("'a'", "Point(1, 2, 3)", SPACE)


def test_answer_picks_the_last_code_span() -> None:
    """A model's explanation yields its last backtick span."""
    assert readable.answer("is `1` or rather `2`") == "2"
    assert readable.answer("plain") == "plain"


def test_score_pairs_each_fact_with_its_answer() -> None:
    """Missing, repeated and unnumbered lines are handled."""
    items = [
        readable.Fact("a", "q1", "1"),
        readable.Fact("b", "q2", "2"),
        readable.Fact("c", "q3", "3"),
    ]
    reply = "preamble\n1: 1\n2) 9\n2. 2\n3: ?\n"
    got = readable.score(items, reply, SPACE)
    assert [(g, ok) for _, g, ok in got] == [
        ("1", True),
        ("9", False),
        ("?", False),
    ]


def test_ask_runs_the_command_with_the_prompt() -> None:
    """The command reads the prompt on stdin; stdout is the reply."""
    code = "import sys; print('1:', len(sys.stdin.read()))"
    assert readable.ask("abcd", [sys.executable, "-c", code]) == "1: 4\n"


def test_ask_runs_in_an_empty_directory_without_thinking() -> None:
    """The command sees no files and MAX_THINKING_TOKENS=0."""
    code = (
        "import os; print(os.listdir('.'), os.environ['MAX_THINKING_TOKENS'])"
    )
    assert readable.ask("", [sys.executable, "-c", code]) == "[] 0\n"


def test_claude_is_the_headless_cli() -> None:
    """The argv names the model and turns tools off."""
    argv = readable.claude("haiku")
    assert argv[:4] == ["claude", "-p", "--model", "haiku"]
    assert "--safe-mode" in argv


def test_chapter_with_and_without_examples() -> None:
    """Chunks are replaced by names; fenced prose can be dropped."""
    text = md(GOOD) + "\nAfter all.\n"
    text = text.replace(
        "`add' sums.", "`add' sums.\n\n```pycon\n>>> 1\n1\n```"
    )
    read = web.read("p.md", text)
    with_ = readable.chapter(read, text)
    without = readable.chapter(read, text, examples=False)
    assert "⟨demo.py⟩" in with_
    assert "def add" not in with_
    assert ">>> 1" in with_
    assert ">>> 1" not in without


def test_tests_for_finds_only_existing_files(tmp_path: Path) -> None:
    """tests/test_<stem>.py per Python file, when it exists."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("")
    text = "```python\n<<a.py>>=\n```\n```python\n<<b/b.py>>=\n```\n"
    text += "```python\n<<n.txt>>=\n```\n"
    got = readable.tests_for(web.read("p.md", text), tmp_path)
    assert got == [tmp_path / "tests" / "test_a.py"]


TESTS = """\
from demo import add


def test_add() -> None:
    assert add(1, 2) == 3
    assert add(2, 2) == 4
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A root with the demo page, its tests and a fake model."""
    page(tmp_path, "demo.md", GOOD)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text(TESTS)
    return tmp_path


def fake(root: Path, reply: str) -> str:
    """A --command that ignores its prompt and prints ``reply``."""
    script = root / "fake.py"
    script.write_text(f"import sys; sys.stdin.read(); print({reply!r})\n")
    return f"{sys.executable} {script}"


def test_cli_scores_a_perfect_reply(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Right answers score 1.00, on the default tests file."""
    cmd = fake(root, "1: 3\n2: 4")
    page_path = str(root / "demo.md")
    assert lit(root, "readable", page_path, "--command", cmd) == 0
    out = capsys.readouterr().out
    assert "run 3: 2/2" in out
    assert "1.00 over 3 run(s) (threshold 0.7)" in out


def test_cli_misses_and_threshold(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong answer is printed; the threshold decides the status."""
    cmd = fake(root, "1: 3\n2: 5")
    args = ["readable", str(root / "demo.md"), "--command", cmd, "--runs", "2"]
    assert lit(root, *args) == 1
    out = capsys.readouterr().out
    assert "run 1 miss " in out
    assert "(expected 4)" in out
    assert "0.50 over 2 run(s)" in out
    assert lit(root, *args, "--threshold", "0.5") == 0


def test_cli_explicit_tests_and_no_examples(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--tests names the test files; --no-examples drops examples."""
    other = root / "other_tests.py"
    other.write_text("def test_x() -> None:\n    assert add(1, 1) == 2\n")
    cmd = fake(root, "1: 2")
    args = ["readable", str(root / "demo.md"), "--command", cmd]
    args += ["--tests", str(other), "--no-examples", "--runs", "1"]
    assert lit(root, *args) == 0
    assert "run 1: 1/1" in capsys.readouterr().out


def test_cli_show_prints_the_prompt(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--show prints the prompt and asks nobody."""
    assert lit(root, "readable", str(root / "demo.md"), "--show") == 0
    out = capsys.readouterr().out
    assert "=== CHAPTER ===" in out
    assert "1. What is `add(1, 2)`?" in out
    assert "⟨demo.py⟩" in out


def test_cli_no_facts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A page without tests has no facts: exit 1."""
    page(tmp_path, "demo.md", GOOD)
    assert lit(tmp_path, "readable", str(tmp_path / "demo.md")) == 1
    assert "no facts in the tests" in capsys.readouterr().out


def test_cli_default_model_command(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without --command the claude CLI is run, found on the PATH."""
    bin_ = root / "bin"
    bin_.mkdir()
    exe = bin_ / "claude"
    exe.write_text(f"#!{sys.executable}\nprint('1: 3\\n2: 4')\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:/usr/bin")
    args = ["readable", str(root / "demo.md"), "--runs", "1"]
    assert lit(root, *args) == 0
    assert "run 1: 2/2" in capsys.readouterr().out
