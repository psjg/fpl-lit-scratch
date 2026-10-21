"""lit weave: a literate page as a CWEB-style book page (prototype quality).

usage: weave.py ROOT PAGE.md OUT.qmd   (run lit.py first: it needs the map)

Numbers every section (prose up to and including at most one chunk) as
§n, heads each chunk ⟨Name n⟩ ≡ (or +≡ for a continuation), turns every
use into a link ⟨Name n⟩, ends a chunk with "This code is used in §m."
and "See also §§…", and closes with three indexes: identifiers (from the
ast of the tangled modules, mapped back through the line map, defining
section in bold), chunk names, and the page's <!-- index: … --> terms.
The output is Pandoc Markdown with raw HTML and raw Typst blocks, for
`quarto render OUT.qmd --to html` and `--to typst`.
"""

import ast
import html
import json
import re
import sys
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

HEAD = re.compile(r"^<<(?P<name>.+?)>>(?P<plus>\+?)=\s*$")
REF = re.compile(r"^(?P<indent>[ \t]*)<<(?P<name>.+?)>>\s*$")
INDEX = re.compile(r"^<!--\s*index:\s*(.+?)\s*-->\s*$")
FENCE = re.compile(r"^```(\w*)")


def norm(name):
    return " ".join(name.split())


def sections(lines, first):
    """[{n, heading, prose, chunk: (name, plus, md_first, body)}]."""
    out, prose, heading, k = [], [], None, 0
    terms = []
    while k < len(lines):
        line = lines[k]
        if line.startswith("#"):
            if any(p.strip() for p in prose):
                out.append({"heading": heading, "prose": prose, "chunk": None})
                heading = None
            prose, heading = [], line
        elif INDEX.match(line):
            terms.append((INDEX.match(line)[1], len(out)))
        elif (fence := FENCE.match(line)) and fence[1] in ("python", "lark"):
            j = k + 1
            while not lines[j].startswith("```"):
                j += 1
            body = lines[k + 1 : j]
            head = HEAD.match(body[0])
            chunk = (norm(head["name"]), head["plus"], first + k + 2, body[1:])
            out.append({"heading": heading, "prose": prose, "chunk": chunk})
            prose, heading, k = [], None, j
        else:
            prose.append(line)
        k += 1
    if any(p.strip() for p in prose):
        out.append({"heading": heading, "prose": prose, "chunk": None})
    for n, s in enumerate(out, 1):
        s["n"] = n
    return out, [(t, i + 1 if i < len(out) else len(out)) for t, i in terms]


def web(secs):
    """name -> {defs: [§], uses: [§]}; md line -> §."""
    names, line_sec = {}, {}
    for s in secs:
        if not s["chunk"]:
            continue
        name, plus, md_first, body = s["chunk"]
        names.setdefault(name, {"defs": [], "uses": []})["defs"].append(s["n"])
        for i, text in enumerate(body):
            line_sec[md_first + 1 + i] = s["n"]
    for s in secs:
        if s["chunk"]:
            for text in s["chunk"][3]:
                if ref := REF.match(text):
                    target = resolve(norm(ref["name"]), names)
                    names[target]["uses"].append(s["n"])
    return names, line_sec


def resolve(name, names):
    if name.endswith("..."):
        hits = [n for n in names if n.startswith(name[:-3])]
        return hits[0]
    return name


def identifiers(root, tangled, line_sec):
    """identifier -> (defining §s, using §s), via ast and the line map."""
    src = (root / tangled).read_text(encoding="utf-8")
    mp = json.loads((root / ".noslop/lit" / (tangled + ".map.json")).read_text())
    t2md = {t: ml for t, _, ml, _ in mp}
    tree = ast.parse(src)
    defs, uses = {}, {}

    def sec(lineno):
        return line_sec.get(t2md.get(lineno, -1))

    for node in tree.body:
        targets = []
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            targets = [node.name]
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for t in targets:
            defs.setdefault(t, set()).add(sec(node.lineno))
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    key = f"{node.name}.{sub.name}"
                    defs.setdefault(key, set()).add(sec(sub.lineno))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and len(node.id) > 1:
            uses.setdefault(node.id, set()).add(sec(node.lineno))
        elif isinstance(node, ast.alias):
            name = (node.asname or node.name).split(".")[-1]
            defs.setdefault(name, set()).add(sec(node.lineno))
    out = {}
    for name in set(defs) | {u for u in uses if u in defs}:
        d = {x for x in defs.get(name, ()) if x}
        u = {x for x in uses.get(name, ()) if x} - d
        out[name] = (sorted(d), sorted(u))
    return out


def label(name, names):
    return f"⟨{name} {names[name]['defs'][0]}⟩"


def chunk_html(s, names):
    name, plus, _, body = s["chunk"]
    sign = "+≡" if plus else "≡"
    rows = []
    fmt = HtmlFormatter(nowrap=True)
    for text in body:
        if ref := REF.match(text):
            t = resolve(norm(ref["name"]), names)
            n = names[t]["defs"][0]
            rows.append(
                f'{html.escape(ref["indent"])}<a class="use" href="#s{n}">'
                f"⟨{html.escape(t)} <small>{n}</small>⟩</a>"
            )
        else:
            rows.append(highlight(text, PythonLexer(), fmt).rstrip("\n"))
    foot = footer(s, names)
    return (
        f'<div class="chunk"><p class="hdr"><em>⟨{html.escape(name)} '
        f"<small>{names[name]['defs'][0]}</small>⟩ {sign}</em></p>\n"
        f'<pre class="highlight"><code>' + "\n".join(rows) + "</code></pre>\n"
        f'<p class="foot">{html.escape(foot)}</p></div>'
    )


def footer(s, names):
    name = s["chunk"][0]
    entry, parts = names[name], []
    if entry["uses"]:
        parts.append(f"This code is used in §{entry['uses'][0]}.")
    elif "/" in name or name.endswith(".py"):
        parts.append("This code is written to the file " + name + ".")
    others = [d for d in entry["defs"] if d != s["n"]]
    if others and s["n"] == entry["defs"][0]:
        parts.append("See also §§" + ", ".join(map(str, others)) + ".")
    return " ".join(parts)


def tq(text):
    return json.dumps(text, ensure_ascii=False)


def chunk_typst(s, names):
    name, plus, _, body = s["chunk"]
    sign = "+≡" if plus else "≡"
    rows = []
    for text in body:
        if ref := REF.match(text):
            t = resolve(norm(ref["name"]), names)
            n = names[t]["defs"][0]
            rows.append(
                f"#raw({tq(ref['indent'])})#link(<s{n}>)[⟨{t} "
                f"#text(size: 0.75em)[{n}]⟩]"
            )
        else:
            rows.append(f'#raw(lang: "python", {tq(text)})')
    foot = footer(s, names)
    return (
        "#block(fill: luma(246), inset: 6pt, radius: 2pt, width: 100%)[\n"
        f"#text(style: \"italic\")[⟨{name} #text(size: 0.75em)"
        f"[{names[name]['defs'][0]}]⟩ {sign}] \\\n"
        + " \\\n".join(rows)
        + f"\n\n#text(size: 0.8em)[{foot}]\n]"
    )


def weave(root, page, out):
    raw = (root / page).read_text(encoding="utf-8").split("\n")
    end = raw.index("---", 1)
    front = raw[1:end]
    title = next(x.split(":", 1)[1].strip() for x in front if x.startswith("title:"))
    secs, terms = sections(raw[end + 1 :], end + 1)
    names, line_sec = web(secs)
    roots = [n for n in names if n.endswith(".py")]
    idents = {}
    for r in roots:
        idents.update(identifiers(root, r, line_sec))
    doc = [
        "---",
        f'title: "{title}"',
        "format:",
        "  html:",
        "    toc: true",
        "    embed-resources: true",
        "    css: weave.css",
        "  typst:",
        "    toc: true",
        "    papersize: a4",
        "---",
        "",
    ]
    for s in secs:
        if s["heading"] and not s["heading"].startswith("# "):
            doc += [s["heading"], ""]
        prose = "\n".join(s["prose"]).strip("\n")
        doc += [f"[]{{#s{s['n']}}}**§{s['n']}.** " + prose, ""]
        if s["chunk"]:
            doc += ["```{=html}", chunk_html(s, names), "```", ""]
            doc += ["```{=typst}", chunk_typst(s, names), "```", ""]
    doc += ["## Index of identifiers", ""]
    for name in sorted(idents, key=str.lower):
        d, u = idents[name]
        refs = [f"**[§{x}](#s{x})**" for x in d] + [f"[§{x}](#s{x})" for x in u]
        doc.append(f"- `{name}`: " + ", ".join(refs))
    doc += ["", "## Index of chunk names", ""]
    for name in sorted(names, key=str.lower):
        e = names[name]
        used = (
            "used in " + ", ".join(f"[§{x}](#s{x})" for x in e["uses"])
            if e["uses"]
            else "a file root"
        )
        doc.append(f"- ⟨{name} [{e['defs'][0]}](#s{e['defs'][0]})⟩: {used}")
    doc += ["", "## Index of concerns", ""]
    for term, n in terms:
        doc.append(f"- {term}: [§{n}](#s{n})")
    Path(out).write_text("\n".join(doc) + "\n", encoding="utf-8")
    css = HtmlFormatter().get_style_defs(".highlight") + CSS
    (Path(out).parent / "weave.css").write_text(css, encoding="utf-8")
    print(f"weave: {len(secs)} sections, {len(names)} chunks, {len(idents)} identifiers")


CSS = """
.chunk { background: #f6f6f4; border-left: 3px solid #bbb; padding: .3em .8em;
  margin: .6em 0 1.2em; }
.chunk pre { background: none; border: 0; margin: 0; padding: 0; }
.chunk .hdr, .chunk .foot { margin: .2em 0; }
.chunk .foot { font-size: .85em; color: #555; }
a.use { font-style: italic; font-family: serif; text-decoration: none; }
"""

if __name__ == "__main__":
    weave(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
