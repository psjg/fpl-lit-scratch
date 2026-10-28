"""The imperative shell: read a bundle from disk into one RDF store.

The walk decides what is bundle. In a git checkout it is the index
(``git ls-files``: tracked and staged files that exist on disk), so an
untracked scratch file never counts and a new note counts once
``git add`` sees it; elsewhere it is every file below the root.
``exclude`` takes path prefixes out of the walk.

Beside the notes, the store takes the fact layer (``facts.py``): every
sidecar ``<page>.facts.json`` of the walk, and every
``build/facts/<page stem>.json`` on disk, the generated layer, which
is never in the index and so is read by name. A rows file with no one
page of its name is a ``fact-load`` finding. In a git checkout one
triple, ``<urn:okf:build> fact:asOf "<HEAD>"``, says which commit the
graph is of.
"""

from __future__ import annotations

import posixpath
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from urllib.parse import unquote

import pyoxigraph as ox

from okfgraph.facts import load_facts, refuse
from okfgraph.project import (
    CLS,
    FACT,
    RDF_TYPE,
    Bundle,
    Context,
    ids_of,
    note_quads,
    okf,
    split,
)

BASE = "https://github.com/fpl-org/fpl/blob/main/"


@dataclass(frozen=True, slots=True)
class Graph:
    """A projected bundle: the store, its node base, what it took."""

    store: ox.Store
    base: str
    files: int
    notes: int
    seconds: float


def context() -> Context:
    """The context shipped beside this module."""
    here = resources.files("okfgraph")
    return Context.load(here.joinpath("context.jsonld").read_text())


def checkout(root: Path) -> bool:
    """Whether ``root`` is a git checkout."""
    return (root / ".git").exists()


def walk(root: Path) -> list[str]:
    """Every bundle file, any suffix, as a sorted POSIX path."""
    if checkout(root):
        cmd = ["git", "-C", str(root), "ls-files", "-z"]
        out = subprocess.run(cmd, check=True, capture_output=True).stdout
        names = out.decode().split("\0")
        return sorted(f for f in names if f and (root / f).is_file())
    found = (p for p in root.rglob("*") if p.is_file())
    return sorted(p.relative_to(root).as_posix() for p in found)


def folders(files: Iterable[str]) -> set[str]:
    """Every folder below the root that holds one of ``files``."""
    out: set[str] = set()
    for f in files:
        while (f := posixpath.dirname(f)) and f not in out:
            out.add(f)
    return out


def kind(path: str, notes: set[str], files: set[str], dirs: set[str]) -> str:
    """A link target that is no note: ``File``, ``Folder`` or ``""``."""
    if path in notes:
        return ""
    if path in files:
        return "File"
    return "Folder" if path in dirs else ""


def head(root: Path) -> str:
    """The commit ``root`` has checked out, or ``""``."""
    if not checkout(root):
        return ""
    cmd = ["git", "-C", str(root), "rev-parse", "--verify", "-q", "HEAD"]
    out = subprocess.run(cmd, capture_output=True, check=False)
    return out.stdout.decode().strip()


def facts(
    store: ox.Store, root: Path, files: list[str], notes: set[str], base: str
) -> None:
    """Load every rows file of the bundle against its page."""
    side = [
        (f, f.removesuffix(".facts.json") + ".md")
        for f in files
        if f.endswith(".facts.json")
    ]
    for p in sorted((root / "build" / "facts").glob("*.json")):
        hits = [n for n in notes if posixpath.basename(n) == p.stem + ".md"]
        page = hits[0] if len(hits) == 1 else ""
        side.append((p.relative_to(root).as_posix(), page))
    for path, page in side:
        if page not in notes:
            store.extend(refuse(path, "no one page of this name"))
            continue
        text = (root / path).read_text(encoding="utf-8")
        load_facts(store, path, text, page, base)
    if sha := head(root):
        at = ox.NamedNode(FACT + "asOf")
        store.add(ox.Quad(ox.NamedNode("urn:okf:build"), at, ox.Literal(sha)))


def build(root: Path, base: str = BASE, exclude: Iterable[str] = ()) -> Graph:
    """Project the bundle at ``root`` onto a fresh store."""
    t0 = time.perf_counter()
    cut = tuple(e.rstrip("/") + "/" for e in exclude)
    files = [f for f in walk(root) if not f.startswith(cut)]
    texts = {
        f: (root / f).read_text(encoding="utf-8", errors="replace")
        for f in files
        if f.endswith(".md")
    }
    ctx = context()
    splits = {f: split(t) for f, t in texts.items()}
    b = Bundle(base, ctx, ids_of(splits))
    quads = [q for f, sp in splits.items() for q in note_quads(f, sp, b)]
    typ = okf("Type")
    quads += [ox.Quad(ox.NamedNode(CLS + t), RDF_TYPE, typ) for t in ctx.types]
    notes, known, dirs = set(texts), set(files), folders(files) | {""}
    targets = {
        q.object.value
        for q in quads
        if isinstance(q.object, ox.NamedNode)
        and q.object.value.startswith(base)
    }
    for iri in sorted(targets):
        path = unquote(iri.removeprefix(base))
        if k := kind(path, notes, known, dirs):
            n = ox.NamedNode(iri)
            quads += [
                ox.Quad(n, RDF_TYPE, okf(k)),
                ox.Quad(n, okf("path"), ox.Literal(path)),
            ]
    store = ox.Store()
    store.extend(quads)
    facts(store, root, files, notes, base)
    took = time.perf_counter() - t0
    return Graph(store, base, len(files), len(texts), took)
