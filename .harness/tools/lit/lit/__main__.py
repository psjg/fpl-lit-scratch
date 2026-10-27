"""lit: the literate pages' tool.

    lit tangle   [PAGE ...]      write each file a page names, read-only
    lit check    [PAGE ...]      the web's rules, and drift: a file
                                 that differs from its page fails at
                                 the page's line
    lit lint     [PAGE ...]      prose and code agree; examples pass
    lit weave OUT [PAGE ...]     each page as OUT/<page>.html
    lit readable PAGE [--tests F ...] [--model M] [--threshold T]
                 [--no-examples] [--command CMD] [--show]
                                 a model answers the tests' facts from
                                 the prose alone; fail below T
    lit run -- CMD ...           run CMD; its output names page lines

Every command takes ``--root DIR`` (default ``.``): file chunks are
written relative to it, and without PAGE every page under it is read.
A finding prints as ``page:line: rule: message -- remedy``. Exit 0:
clean; 1: a finding, or a score below the threshold; 2: usage.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

from lit import lint, readable, run, web


def pages(root: Path, named: list[str]) -> list[tuple[web.Page, str]]:
    """The pages named, or all pages under the root, with their text."""
    paths = [Path(p) for p in named] or web.discover(root)
    out: list[tuple[web.Page, str]] = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        shown = p.resolve().relative_to(root.resolve()).as_posix()
        out.append((web.read(shown, text), text))
    return out


def tangled(
    found: list[tuple[web.Page, str]],
) -> tuple[list[tuple[web.Page, list[web.Tangled]]], list[web.Finding]]:
    """Each page's files, and every finding of the webs."""
    out: list[tuple[web.Page, list[web.Tangled]]] = []
    findings: list[web.Finding] = []
    owner: dict[str, str] = {}
    for page, _ in found:
        files, bad = web.tangle(page)
        findings += bad
        for t in files:
            if t.name in owner:
                message = f"{t.name} is also a file of {owner[t.name]}"
                findings.append(web.Finding(page.path, 1, "lit-web", message))
            owner.setdefault(t.name, page.path)
        out.append((page, files))
    return out, findings


def report(findings: list[web.Finding], verb: str, count: int) -> int:
    """Print the findings and a summary; the exit status."""
    for f in findings:
        print(f)
    print(f"lit {verb}: {count} page(s), {len(findings)} finding(s)")
    return 1 if findings else 0


def drift(t: web.Tangled, root: Path) -> web.Finding | None:
    """Where the file on disk first differs from its tangle, if so."""
    disk = root / t.name
    if not disk.is_file():
        message = f"{t.name} is missing -- run lit tangle"
        return web.Finding(
            t.page, t.origin[0] if t.origin else 1, "lit-drift", message
        )
    held = disk.read_bytes().split(b"\n")
    fresh = t.text.encode().split(b"\n")
    if held == fresh:
        return None
    k = next(
        (
            i
            for i, (a, b) in enumerate(zip(held, fresh, strict=False))
            if a != b
        ),
        min(len(held), len(fresh)) - 1,
    )
    line = t.origin[min(k, len(t.origin) - 1)] if t.origin else 1
    message = (
        f"{t.name}:{k + 1} differs from the page -- edit the page, not the"
        " file, then run lit tangle"
    )
    return web.Finding(t.page, line, "lit-drift", message)


def write(t: web.Tangled, root: Path) -> bool:
    """Write a tangled file read-only, if its bytes differ; whether."""
    disk = root / t.name
    data = t.text.encode()
    if disk.is_file() and disk.read_bytes() == data:
        disk.chmod(0o444)
        return False
    disk.parent.mkdir(parents=True, exist_ok=True)
    if disk.exists():
        disk.chmod(0o644)
    disk.write_bytes(data)
    disk.chmod(0o444)
    return True


def cmd_tangle(args: argparse.Namespace) -> int:
    """Write every file, unless a web has a finding."""
    found = pages(args.root, args.pages)
    webs, findings = tangled(found)
    if findings:
        return report(findings, "tangle", len(found))
    files = [t for _, ts in webs for t in ts]
    started = time.perf_counter()
    written = sum(write(t, args.root) for t in files)
    ms = (time.perf_counter() - started) * 1000
    print(f"lit tangle: {len(files)} file(s), {written} written, {ms:.0f} ms")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """The web's findings, and each file's drift."""
    found = pages(args.root, args.pages)
    webs, findings = tangled(found)
    for _, files in webs:
        findings += [d for t in files if (d := drift(t, args.root))]
    return report(findings, "check", len(found))


def cmd_lint(args: argparse.Namespace) -> int:
    """The names and the examples of every page."""
    found = pages(args.root, args.pages)
    webs, findings = tangled(found)
    for page, files in webs:
        findings += lint.names(page, files)
        findings += lint.examples(page, files, args.root.resolve())
    return report(findings, "lint", len(found))


def cmd_weave(args: argparse.Namespace) -> int:
    """Write each page's HTML."""
    from lit import weave  # noqa: PLC0415 -- only weave needs markdown-it

    found = pages(args.root, args.pages)
    webs, findings = tangled(found)
    args.out.mkdir(parents=True, exist_ok=True)
    for (page, files), (_, text) in zip(webs, found, strict=True):
        title = next(
            (ln[2:] for ln in text.split("\n") if ln.startswith("# ")),
            page.path,
        )
        out = args.out / (Path(page.path).stem + ".html")
        out.write_text(weave.weave(page, files, title), encoding="utf-8")
        print(f"lit weave: {out}")
    return report(findings, "weave", len(found))


def cmd_readable(args: argparse.Namespace) -> int:
    """Ask the model; print each fact's verdict and the score."""
    [(page, text)] = pages(args.root, [args.page])
    files, _ = web.tangle(page)
    known, _ = lint.code_names(files)
    tests = [Path(t) for t in args.tests] or readable.tests_for(
        page, args.root
    )
    items = [
        f
        for p in tests
        for f in readable.facts(
            p.as_posix(), p.read_text(encoding="utf-8"), known
        )
    ]
    if not items:
        print("lit readable: no facts in the tests -- name them with --tests")
        return 1
    prompt = readable.prompt(
        readable.chapter(page, text, examples=args.examples), items
    )
    if args.show:
        print(prompt)
        return 0
    command = (
        shlex.split(args.command)
        if args.command
        else readable.claude(args.model)
    )
    module = next(t for t in files if t.name.endswith(".py"))
    space = lint.load(module, args.root.resolve())
    shares: list[float] = []
    for n in range(1, args.runs + 1):
        reply = readable.ask(prompt, command)
        verdicts = readable.score(items, reply, space)
        right = sum(ok for _, _, ok in verdicts)
        for fact, got, ok in verdicts:
            if not ok:
                print(
                    f"run {n} miss {fact.anchor}: {fact.question} -> {got}"
                    f" (expected {fact.expected})"
                )
        shares.append(right / len(verdicts))
        print(f"lit readable: run {n}: {right}/{len(verdicts)}")
    share = sum(shares) / len(shares)
    print(
        f"lit readable: {share:.2f} over {args.runs} run(s)"
        f" (threshold {args.threshold})"
    )
    return 0 if share >= args.threshold else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run the command; rewrite its output to page places."""
    found = pages(args.root, args.pages_)
    webs, _ = tangled(found)
    files = run.table([t for _, ts in webs for t in ts], args.root)
    done = subprocess.run(
        args.argv, capture_output=True, text=True, check=False
    )
    sys.stdout.write(run.rewrite(done.stdout, files, args.root))
    sys.stderr.write(run.rewrite(done.stderr, files, args.root))
    return done.returncode


def parser() -> argparse.ArgumentParser:
    """The command line."""
    top = argparse.ArgumentParser(prog="lit", description="literate pages")
    top.add_argument("--root", type=Path, default=Path())
    sub = top.add_subparsers(dest="cmd", required=True)
    for name, fn in (
        ("tangle", cmd_tangle),
        ("check", cmd_check),
        ("lint", cmd_lint),
    ):
        p = sub.add_parser(name)
        p.add_argument("pages", nargs="*")
        p.set_defaults(fn=fn)
    p = sub.add_parser("weave")
    p.add_argument("out", type=Path)
    p.add_argument("pages", nargs="*")
    p.set_defaults(fn=cmd_weave)
    p = sub.add_parser("readable")
    p.add_argument("page")
    p.add_argument("--tests", nargs="*", default=[])
    p.add_argument("--model", default=readable.MODEL)
    p.add_argument("--threshold", type=float, default=readable.THRESHOLD)
    p.add_argument("--runs", type=int, default=readable.RUNS)
    p.add_argument("--no-examples", dest="examples", action="store_false")
    p.add_argument("--command")
    p.add_argument("--show", action="store_true")
    p.set_defaults(fn=cmd_readable)
    p = sub.add_parser("run")
    p.add_argument("--page", dest="pages_", action="append", default=[])
    p.add_argument("argv", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_run)
    return top


def main(argv: list[str] | None = None) -> int:
    """Dispatch a subcommand; its exit status."""
    args = parser().parse_args(argv)
    if getattr(args, "argv", None) and args.argv[0] == "--":
        args.argv = args.argv[1:]
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())
