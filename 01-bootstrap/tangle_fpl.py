"""
Tangle 03-fpl/**/*.md (except OLD/) into sibling *.fpl files.

Markdown is the source. Prose becomes `;` line comments. Fenced blocks
with info `fpl` or empty become raw source. Other fences are skipped.
Front matter is stripped. A .fpl without a matching .md is an error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / "03-fpl"
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
FENCE = re.compile(r"```([^\n]*)\n(.*?)```", re.S)


def sources() -> list[Path]:
    return sorted(
        p
        for p in IMAGE.rglob("*.md")
        if "OLD" not in p.parts
        and p.name not in {"README.md", "index.md"}
    )


def comment_prose(prose: str) -> str:
    body = prose.strip("\n")
    if not body.strip():
        return ""
    lines: list[str] = []
    for line in body.split("\n"):
        if line.strip() == "":
            lines.append(";")
        else:
            lines.append(f"; {line}" if not line.startswith(" ") else f";{line}")
    return "\n".join(lines)


def tangle_text(text: str) -> str:
    body = FRONT_MATTER.sub("", text, count=1)
    parts: list[str] = []
    cursor = 0
    for match in FENCE.finditer(body):
        prose = comment_prose(body[cursor : match.start()])
        if prose:
            parts.append(prose)
        info = match.group(1).strip().split()
        lang = info[0].lower() if info else "fpl"
        if lang in ("", "fpl"):
            source = match.group(2)
            if source.endswith("\n"):
                source = source[:-1]
            parts.append(source)
        cursor = match.end()
    tail = comment_prose(body[cursor:])
    if tail:
        parts.append(tail)
    out = "\n\n".join(parts).strip() + "\n"
    return out


def orphan_fpls() -> list[Path]:
    bad: list[Path] = []
    for fpl in IMAGE.rglob("*.fpl"):
        if "OLD" in fpl.parts:
            continue
        if not fpl.with_suffix(".md").is_file():
            bad.append(fpl)
    return bad


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if any .fpl is stale or orphaned",
    )
    args = parser.parse_args(argv)

    orphans = orphan_fpls()
    if orphans:
        for path in orphans:
            print(f"tangle-fpl: orphan {path.relative_to(ROOT)} (no .md)", file=sys.stderr)
        return 1

    stale = False
    for md in sources():
        fpl = md.with_suffix(".fpl")
        text = tangle_text(md.read_text(encoding="utf-8"))
        if args.check:
            if not fpl.is_file() or fpl.read_text(encoding="utf-8") != text:
                print(f"tangle-fpl: stale {fpl.relative_to(ROOT)}", file=sys.stderr)
                stale = True
            continue
        fpl.write_text(text, encoding="utf-8")
        print(fpl.relative_to(ROOT))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
