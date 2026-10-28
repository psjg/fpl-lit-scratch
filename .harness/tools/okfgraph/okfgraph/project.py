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
typed body links    ``body:<key>`` besides ``okf:linksTo``, for a link
                    that is the value of an inline field
                    (``key:: [x](y.md)``, ``[key:: [x](y.md)]``) or
                    whose title is a key (``[x](y.md "key")``), when
                    the context declares ``key`` an edge; any other
                    key is ``okf:undeclaredField`` or
                    ``okf:undeclaredTitle``, a literal for a report
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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from itertools import groupby
from typing import cast
from urllib.parse import quote, unquote

import pyoxigraph as ox
import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token

OKF = "https://fpl-org.github.io/okf#"
CLS = "https://fpl-org.github.io/okf/type#"
KEY = "https://fpl-org.github.io/okf/key#"
REL = "https://fpl-org.github.io/okf/rel#"
BODY = "https://fpl-org.github.io/okf/body#"
FACT = "https://fpl-org.github.io/okf/fact#"
PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "okf": OKF,
    "cls": CLS,
    "key": KEY,
    "rel": REL,
    "body": BODY,
    "fact": FACT,
}
RESERVED = frozenset({"index.md", "log.md"})  # OKF §3.1: not concepts
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")  # http:, mailto:, urn:
MDLINK = re.compile(
    r"^\s*\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)\s*$"
)
WIKILINK = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
ADR_ID = re.compile(r"^([A-Za-z]+-\d+)-")  # ADR-0003-slug -> ADR-0003
FENCE_END = re.compile(r"^(---|\.\.\.)\s*$", re.M)
FIELD_KEY = r"[A-Za-z][\w-]*(?:[ \t]+[\w-]+)*"  # Dataview: words, dashes
LINE_FIELD = re.compile(rf"^\s*({FIELD_KEY})::")  # key:: at a line's start
BRACKET = re.compile(rf"\[\s*({FIELD_KEY})::|\]")  # [key:: opens, ] closes
# text_join off: an escaped \[ stays a token apart and opens no field.
BREAKS = ("softbreak", "hardbreak")
MD = MarkdownIt("commonmark").enable("table").disable("text_join")
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
class Link:
    """One body link or image, and the relation the body writes for it.

    ``field`` is the key of the inline field the link is a value of,
    ``title`` the link's title; both as written, ``""`` when absent.
    """

    kind: str
    href: str
    field: str = ""
    title: str = ""


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


def links(body: str) -> tuple[list[Link], list[str]]:
    """The links and images of a body; its wikilinks.

    A real CommonMark parser, not a regex: a link inside a code span or
    fence is no edge, and a reference-style link resolves.
    """
    found: list[Link] = []
    wikis: list[str] = []
    for tok in MD.parse(body):
        if tok.children:
            found += Fields().read(tok.children)
            wikis += wikilinks(tok.children)
    return found, wikis


def wikilinks(children: Sequence[Token]) -> list[str]:
    """The wikilinks of one inline run: in each stretch of text."""
    runs = groupby(children, lambda c: c.type in ("text", "text_special"))
    texts = ("".join(c.content for c in run) for ok, run in runs if ok)
    return [w for t in texts for w in WIKILINK.findall(t)]


@dataclass(slots=True)
class Fields:
    """The links of one inline run, with the field each is a value of.

    The run is read line by line (a soft or hard break ends a line,
    but not one inside a link label, which a wrapped label holds).
    ``key::`` in the text that opens a line makes every link after it
    on that line a value of ``key``. ``[key::`` in plain text opens a
    bracketed field, the next plain ``]`` closes it, and the links in
    between are its values; a bracket the line never closes gives its
    links no key of its own. Link labels and escapes are not plain
    text, so ``\\[`` and ``\\]`` open and close nothing.
    """

    found: list[Link] = field(default_factory=list[Link])
    held: list[Link] = field(default_factory=list[Link])  # bracket values
    key: str = ""  # the line's field
    bracket: str = ""  # the open bracket's field
    label: bool = False  # inside a link's label
    start: bool = True  # at a line's first token

    def read(self, children: Sequence[Token]) -> list[Link]:
        """Feed every token, then end the last line."""
        for c in children:
            self.feed(c)
            self.start = c.type in BREAKS and not self.label
        self.close("")
        return self.found

    def feed(self, c: Token) -> None:
        """Take one token: a line break, plain text, a link or image."""
        if c.type in BREAKS and not self.label:
            self.close("")
            self.key = self.bracket = ""
        elif c.type == "text" and not self.label:
            self.text(c.content)
        elif c.type in ("link_open", "link_close"):
            self.label = c.type == "link_open"
            if self.label:
                href, title = c.attrGet("href"), c.attrGet("title")
                ln = Link(
                    "linksTo", str(href or ""), self.key, str(title or "")
                )
                (self.held if self.bracket else self.found).append(ln)
        elif c.type == "image":
            self.found.append(Link("embeds", str(c.attrGet("src") or "")))

    def text(self, content: str) -> None:
        """Plain text: a line's ``key::``, a bracket opened, closed."""
        if self.start and (m := LINE_FIELD.match(content)):
            self.key = m.group(1)
        for m in BRACKET.finditer(content):
            self.close(self.bracket if m.group(1) is None else "")
            self.bracket = m.group(1) or ""

    def close(self, key: str) -> None:
        """Release the held bracket values, typed by ``key`` if any."""
        self.found += [replace(x, field=key) if key else x for x in self.held]
        self.held.clear()


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
    s: ox.NamedNode, path: str, body: str, b: Bundle
) -> list[ox.Quad]:
    """The quads of a body: links, typed links, images, wikilinks."""
    q: list[ox.Quad] = []
    found, wikis = links(body)
    for link in found:
        href = link.href.strip()
        if not href or href.startswith("#"):
            continue
        if SCHEME.match(href):
            q.append(ox.Quad(s, okf("linksToExternal"), ox.Literal(href)))
            q += typed(s, link, iri, b.ctx) if (iri := absolute(href)) else []
            continue
        dest = resolve(href, path)
        if dest is None:
            continue
        if outside(dest):
            q.append(ox.Quad(s, okf("linksOutside"), ox.Literal(dest)))
        else:
            o = node(b.base, dest)
            q += [ox.Quad(s, okf(link.kind), o), *typed(s, link, o, b.ctx)]
    wiki = okf("wikilink")
    return q + [ox.Quad(s, wiki, ox.Literal(w.strip())) for w in wikis]


def absolute(href: str) -> ox.NamedNode | None:
    """An external href as an IRI; ``None`` for one that is no IRI.

    markdown-it percent-encodes a destination, yet not into a valid
    IRI every time (``http://[::1``); such a link stays a literal.
    """
    try:
        return ox.NamedNode(href)
    except ValueError:
        return None


def typed(
    s: ox.NamedNode, link: Link, o: ox.NamedNode, ctx: Context
) -> list[ox.Quad]:
    """The typed edges a body link's field and title give it.

    A key is normalised as Dataview does (trimmed, lower case, inner
    whitespace a ``-``), which is the spelling of the frontmatter key
    the context declares. A key the context does not declare an edge
    is kept as a literal ``key -> href`` for the report, never typed.
    """
    q: list[ox.Quad] = []
    for form, raw in (("Field", link.field), ("Title", link.title)):
        key = "-".join(raw.split()).lower()
        if key in ctx.edges:
            q.append(ox.Quad(s, ox.NamedNode(BODY + quote(key, safe="")), o))
        elif key:
            note = ox.Literal(f"{raw.strip()} -> {link.href}")
            q.append(ox.Quad(s, okf("undeclared" + form), note))
    return q


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
    return q + body_quads(s, path, sp.body, b)
