"""Prototype weave: one page to Pandoc Markdown with CWEB-style numbers, xrefs and an index."""
import ast, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import lit

root, page = Path(sys.argv[1]), sys.argv[2]
defs, files, uses, width, errors = lit.tangle(root, markers=False)
slug = "s"
first = {n: ps[0] for n, ps in defs.items()}
mine = sorted((p for ps in defs.values() for p in ps if p.page == page), key=lambda p: p.line)
users: dict[str, list[int]] = {}
for p in mine:
    for t in p.body:
        r = lit.REF.match(t)
        if r: users.setdefault(r["name"], []).append(p.section)
def lab(n): return f"⟨{n} {first[n].section}⟩"
def lnk(k): return f"[§{k}](#{slug}{k})"
src = (root / page).read_text().split("\n")
out = list(src)
for p in sorted(mine, key=lambda p: -p.line):
    fence, dl, end = p.line - 3, p.line - 2, p.line - 1 + len(p.body)
    for i, t in enumerate(p.body):
        r = lit.REF.match(t)
        if r: out[p.line - 1 + i] = r["indent"] + lab(r["name"])
    out[dl] = f"{lab(p.name)} {'+≡' if p.op else '≡'}"
    out[fence] = "```{.python #%s%d}" % (slug, p.section)
    foot = []
    if lit.ROOT.match(p.name): foot.append(f"This code is written to file `{p.name}`.")
    elif p is first[p.name]:
        foot.append("This code is used in " + ", ".join(lnk(k) for k in users.get(p.name, [])) + ".")
        more = [q.section for q in defs[p.name][1:]]
        if more: foot.append("See also " + ", ".join(lnk(k) for k in more) + ".")
    out[end + 1:end + 1] = ["", f"::: {{.xref}}\n{' '.join(foot)}\n:::"]
    out.insert(fence, f"**§{p.section}.**" if not p.op else f"**§{p.section}.**")
text = "\n".join(out)
text = re.sub(r"`<<([^<>]+)>>`", lambda m: f"[{lab(m[1])}](#{slug}{first[m[1]].section})", text)
# identifier index from the tangled code, mapped back to sections
lines = files["fpl/lex.py"]
code = lit.text_of(lines)
sec_of = {}
for p in mine:
    for i in range(len(p.body)): sec_of[(p.page, p.line + i)] = p.section
def sec(lineno):
    o = lines[lineno - 1][1]
    return sec_of.get(tuple(o)) if o else None
defined, used = {}, {}
tree = ast.parse(code)
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)): defined[node.name] = sec(node.lineno)
    if isinstance(node, ast.ClassDef):
        for m in node.body:
            if isinstance(m, ast.FunctionDef) and not m.name.startswith("__"): defined[f"{node.name}.{m.name}"] = sec(m.lineno)
            if isinstance(m, ast.AnnAssign) and isinstance(m.target, ast.Name): defined[f"{node.name}.{m.target.id}"] = sec(m.lineno)
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name): defined[t.id] = sec(node.lineno)
def locals_of(fn):
    names = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store): names.add(n.id)
    return names
def visit(node, local, cls):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.Lambda)) and not isinstance(child, ast.Lambda):
            visit(child, local | locals_of(child), cls)
            continue
        if isinstance(child, ast.ClassDef):
            visit(child, local, child.name); continue
        name = None
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id not in local:
            name = child.id
        if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id == "self" and cls:
            name = f"{cls}.{child.attr}"
        if name in defined:
            s = sec(child.lineno)
            if s and s != defined[name]: used.setdefault(name, set()).add(s)
        visit(child, local, cls)
visit(tree, set(), None)
idx = ["", "## Index", "", "Every identifier the page defines, with the section that defines it in bold and the sections that use it.", ""]
for k in sorted(defined, key=str.lower):
    refs = [f"**{lnk(defined[k])}**"] + [lnk(s) for s in sorted(used.get(k, ()))]
    idx.append(f"- `{k}`: " + ", ".join(refs))
idx += ["", "## Names of the sections", ""]
for n in sorted(first, key=str.lower):
    if first[n].page == page: idx.append(f"- {lab(n)}: {lnk(first[n].section)}")
print(text + "\n".join(idx))
