"""The functional core: one OKF note in, its RDF quads out.

The bundle stays the source of truth (YAML frontmatter and relative
markdown links, no wikilinks); the graph is a read-only projection:

==================  ==================================================
OKF                 RDF
==================  ==================================================
each ``.md`` file   ``<path> a okf:Document ; okf:path "path"``
``type: ADR``       ``a cls:ADR`` and ``okf:type "ADR"``
frontmatter keys    JSON-LD over ``context.jsonld``: a term typed
                    ``"@type": "@id"`` (``supersedes``, ``affects``)
                    is a typed edge, any other key a literal under
                    ``@vocab``. An edge value is a bare id, a path
                    (relative, or bundle-absolute ``/path``) or a
                    quoted markdown link ``"[x](y.md)"``; a key whose
                    value is such a link is an edge, typed by the key
body links          ``okf:linksTo``, untyped, as OKF §6.1 has it
body images         ``okf:embeds``
``[[wikilinks]]``   ``okf:wikilink "name"``: a literal, since OKF does
                    not follow them; reported, never resolved
==================  ==================================================

A node's IRI is the base IRI followed by its percent-encoded bundle
path. Every edge target is resolved here, never by the JSON-LD
processor, so the base may carry a path of its own (the default is the
repository's page on the forge). A bare id resolves through the id
index (file stems, ``ADR-NNNN`` prefixes and ``id:`` keys); an id no
file answers to becomes ``<urn:okf:id:...>`` and a path above the
bundle root ``<urn:okf:outside:...>``, so the dangling gate finds both.
"""

from __future__ import annotations

import datetime as dt
import json
import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from urllib.parse import quote, unquote

import pyoxigraph as ox
import yaml
from markdown_it import MarkdownIt

OKF = "https://fpl-org.github.io/okf#"
CLS = "https://fpl-org.github.io/okf/type#"
KEY = "https://fpl-org.github.io/okf/key#"
REL = "https://fpl-org.github.io/okf/rel#"
PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "okf": OKF,
    "cls": CLS,
    "key": KEY,
    "rel": REL,
}
RESERVED = frozenset({"index.md", "log.md"})  # OKF §3.1: not concepts
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")  # http:, mailto:, urn:
MDLINK = re.compile(
    r"^\s*\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)\s*$"
)
WIKILINK = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
ADR_ID = re.compile(r"^([A-Za-z]+-\d+)-")  # ADR-0003-slug -> ADR-0003
FENCE_END = re.compile(r"^(---|\.\.\.)\s*$", re.M)
MD = MarkdownIt("commonmark").enable("table")
RDF_TYPE = ox.NamedNode(PREFIXES["rdf"] + "type")

type Ids = Mapping[str, str | None]


@dataclass(frozen=True, slots=True)
class Split:
    """A note cut at its frontmatter.

    ``state`` is ``"none"`` (no leading ``---`` block), ``"invalid"``
    (the block is not a YAML mapping; ``error`` says why) or ``"ok"``.
    """

    state: str
    front: dict[str, object]
    body: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class Context:
    """The parsed ``context.jsonld``: the context, edge keys, types."""

    jsonld: dict[str, object]
    edges: frozenset[str]
    types: frozenset[str]

    @classmethod
    def load(cls, text: str) -> Context:
        """Read a context; a term mapped to ``cls:<Name>`` is a type."""
        ctx: dict[str, object] = json.loads(text)["@context"]
        edges = frozenset(
            k
            for k, v in ctx.items()
            if isinstance(v, dict)
            and cast("dict[str, object]", v).get("@type") == "@id"
        )
        types = frozenset(
            k for k, v in ctx.items() if isinstance(v, str) and v == f"cls:{k}"
        )
        return cls(ctx, edges, types)


@dataclass(frozen=True, slots=True)
class Bundle:
    """What every note is projected against: base IRI, context, ids."""

    base: str
    ctx: Context
    ids: Ids


def node(base: str, path: str) -> ox.NamedNode:
    """The IRI of a bundle path; ``quote`` keeps ``/`` and ``-._~``."""
    return ox.NamedNode(base + quote(path))


def okf(local: str) -> ox.NamedNode:
    """A term of the okf: vocabulary."""
    return ox.NamedNode(OKF + local)


def split(text: str) -> Split:
    """Cut a note into frontmatter and body.

    A broken block is reported in the result, never swallowed.
    """
    if not text.startswith("---\n"):
        return Split("none", {}, text)
    end = FENCE_END.search(text, 4)
    if end is None:
        return Split("invalid", {}, text, "unclosed frontmatter")
    body = text[end.end() :]
    try:
        front: object = yaml.safe_load(text[4 : end.start()])
    except yaml.YAMLError as e:
        return Split("invalid", {}, body, str(e).splitlines()[0])
    if front is None:
        return Split("ok", {}, body)
    if not isinstance(front, dict):
        kind = type(front).__name__
        return Split("invalid", {}, body, f"frontmatter is a {kind}")
    items = cast("dict[object, object]", front).items()
    return Split("ok", {str(k): jsonable(v) for k, v in items}, body)


def jsonable(v: object) -> object:
    """A YAML value as JSON carries it: ISO dates, string keys."""
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, dict):
        items = cast("dict[object, object]", v).items()
        return {str(k): jsonable(x) for k, x in items}
    if isinstance(v, list):
        return [jsonable(x) for x in cast("list[object]", v)]
    return v


def resolve(href: str, src: str) -> str | None:
    """Resolve a link against note ``src``; ``None`` for ``#anchor``.

    ``/x`` is bundle-absolute, anything else relative to the folder of
    ``src``. The bundle root is ``""``, however it is spelled (``/``,
    ``./`` at the root, ``../`` one level down). The result starts with
    ``..`` when it climbs out of the bundle; callers report that, never
    clamp it.
    """
    path = unquote(href.split("#", 1)[0].split("?", 1)[0])
    if not path:
        return None
    if path.startswith("/"):
        path = path.lstrip("/") or "."
    else:
        path = posixpath.join(posixpath.dirname(src), path)
    path = posixpath.normpath(path)
    return "" if path == "." else path


def outside(path: str) -> bool:
    """True for a resolved path that climbs out of the bundle."""
    return path == ".." or path.startswith("../")


def target(value: object, src: str, b: Bundle) -> str | None:
    """The IRI one frontmatter edge value names; ``None`` when empty.

    A quoted markdown link is read for its target; an absolute IRI
    stays as it is; a path is anything holding ``/``, or ending in
    ``.md`` once a ``#fragment`` and ``?query`` are cut off; every other
    value is a bare id.
    """
    if value is None or value == "":
        return None
    text = str(value).strip()
    if m := MDLINK.match(text):
        text = m.group(1)
    if SCHEME.match(text):
        return text
    bare = text.split("#", 1)[0].split("?", 1)[0]
    if "/" in text or not bare or bare.endswith(".md"):
        path = resolve(text, src)
        if path is None:
            return None
        if outside(path):
            return "urn:okf:outside:" + quote(path)
        return b.base + quote(path)
    hit = b.ids.get(text)
    return b.base + quote(hit) if hit else "urn:okf:id:" + quote(text)


def links(body: str) -> tuple[list[tuple[str, str]], list[str]]:
    """The links and images of a body as ``(kind, href)``; wikilinks.

    A real CommonMark parser, not a regex: a link inside a code span or
    fence is no edge, and a reference-style link resolves.
    """
    found: list[tuple[str, str]] = []
    wikis: list[str] = []
    for tok in MD.parse(body):
        for child in tok.children or []:
            if child.type == "link_open":
                found.append(("linksTo", str(child.attrGet("href") or "")))
            elif child.type == "image":
                found.append(("embeds", str(child.attrGet("src") or "")))
            elif child.type == "text":
                wikis += WIKILINK.findall(child.content)
    return found, wikis


def ids_of(notes: Mapping[str, Split]) -> dict[str, str | None]:
    """Bare id to bundle path: stems, ``ADR-NNNN-`` prefixes, ``id:``.

    An id two files claim maps to ``None``: ambiguous, so ``target``
    leaves it unresolved rather than guess.
    """
    ids: dict[str, str | None] = {}

    def claim(key: str, path: str) -> None:
        ids[key] = path if ids.get(key, path) == path else None

    for path, sp in notes.items():
        stem = posixpath.basename(path).removesuffix(".md")
        claim(stem, path)
        if m := ADR_ID.match(stem):
            claim(m.group(1), path)
        if isinstance(own := sp.front.get("id"), str):
            claim(own, path)
    return ids


def kind_quads(s: ox.NamedNode, kind: object) -> list[ox.Quad]:
    """The quads of a note's ``type``: its class, or why it has none."""
    if isinstance(kind, str) and kind.strip():
        cls = ox.NamedNode(CLS + quote(kind.strip(), safe=""))
        return [
            ox.Quad(s, RDF_TYPE, cls),
            ox.Quad(s, okf("type"), ox.Literal(kind.strip())),
        ]
    if kind is not None:
        return [ox.Quad(s, okf("typeError"), ox.Literal(repr(kind)))]
    return []


def front_quads(
    s: ox.NamedNode, path: str, front: dict[str, object], b: Bundle
) -> list[ox.Quad]:
    """The quads of a frontmatter: type, typed edges and literals."""
    front = dict(front)
    q = kind_quads(s, front.pop("type", None))
    local: dict[str, object] = {}
    doc: dict[str, object] = {}
    for k, v in front.items():
        if k.startswith("@"):
            continue
        vals = cast("list[object]", v) if isinstance(v, list) else [v]
        if k not in b.ctx.edges and any(
            isinstance(x, str) and MDLINK.match(x) for x in vals
        ):
            local[k] = {"@id": REL + quote(k, safe=""), "@type": "@id"}
        if k in b.ctx.edges or k in local:
            doc[k] = [t for t in (target(x, path, b) for x in vals) if t]
        else:
            doc[k] = v
    doc["@context"] = [b.ctx.jsonld, local] if local else b.ctx.jsonld
    doc["@id"] = s.value
    try:
        data = json.dumps(doc).encode()
        triples = ox.parse(data, format=ox.RdfFormat.JSON_LD)
        q += [ox.Quad(t.subject, t.predicate, t.object) for t in triples]
    except SyntaxError as e:
        err = ox.Literal(f"json-ld: {e}")
        q.append(ox.Quad(s, okf("frontmatterError"), err))
    return q


def body_quads(
    s: ox.NamedNode, path: str, body: str, base: str
) -> list[ox.Quad]:
    """The quads of a body: its links, images and wikilinks."""
    q: list[ox.Quad] = []
    found, wikis = links(body)
    for kind, raw in found:
        href = raw.strip()
        if not href or href.startswith("#"):
            continue
        if SCHEME.match(href):
            q.append(ox.Quad(s, okf("linksToExternal"), ox.Literal(href)))
            continue
        dest = resolve(href, path)
        if dest is None:
            continue
        if outside(dest):
            q.append(ox.Quad(s, okf("linksOutside"), ox.Literal(dest)))
        else:
            q.append(ox.Quad(s, okf(kind), node(base, dest)))
    wiki = okf("wikilink")
    return q + [ox.Quad(s, wiki, ox.Literal(w.strip())) for w in wikis]


def note_quads(path: str, sp: Split, b: Bundle) -> list[ox.Quad]:
    """Every quad of one note. Pure: the same inputs, the same quads."""
    s = node(b.base, path)
    q = [
        ox.Quad(s, RDF_TYPE, okf("Document")),
        ox.Quad(s, okf("path"), ox.Literal(path)),
        ox.Quad(s, okf("frontmatter"), ox.Literal(sp.state)),
    ]
    if posixpath.basename(path) in RESERVED:
        q.append(ox.Quad(s, RDF_TYPE, okf("Reserved")))
    if sp.state == "invalid":
        err = ox.Literal(sp.error)
        q.append(ox.Quad(s, okf("frontmatterError"), err))
    q += front_quads(s, path, sp.front, b)
    return q + body_quads(s, path, sp.body, b.base)
