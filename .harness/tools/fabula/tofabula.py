"""Zet een stepdemo-trace om naar de fabula: de uitvoering als tekst.

Gebruik: python3 -I tofabula.py TRACE.json OUT.fabula.json

Per run (sleutel: ``call``, zoals de profielnaam ``<call> · <maat>`` van
tospeedscope.py) één rij per stap::

    {ln, file, src, f, frame: {name, file, parent}, u, ops: [{off, op, arg}] | null}

``file`` is een index in ``files``; ``src`` is de bronregel van schijf
(``sources`` in de trace is leeg of een fragment). ``ops`` is null als de
trace de stap geen offsets gaf: de gesynthetiseerde ``__init__`` van een
dataclass, en code zonder disassembly (errors.py). Zo'n stap telt ``u``
lege rijen, zodat de υ-strook gelijk blijft met de as.

``files`` geeft per bestand alle regels (het syuzhet), ``dis`` per bestand
en regel de statische disassembly ``[off, op, arg, code]`` over alle code
objecten van de run.
"""

import json
import sys


def convert(runs):
    """De fabula van alle runs; ``files`` en ``dis`` zijn gedeeld."""
    paths, lines, dis, out = [], [], [], {}

    def fidx(path):
        """Index van een bestand; leest het de eerste keer van schijf."""
        if path not in paths:
            paths.append(path)
            with open(path, encoding="utf-8") as f:
                lines.append(f.read().split("\n"))
            dis.append({})
        return paths.index(path)

    for run in runs:
        codes = run["codes"]
        for c, ins in run["bytecode"].items():
            fi = fidx(codes[int(c)]["file"])
            for off, op, arg, ln, _ in ins:
                if ln is None:
                    continue
                row = [off, op, arg, int(c)]
                bucket = dis[fi].setdefault(str(ln), [])
                if row not in bucket:
                    bucket.append(row)
        steps = []
        for s in run["steps"]:
            fr = run["frames"][s["f"]]
            code = codes[fr["code"]]
            fi = fidx(code["file"])
            bc = {e[0]: e for e in run["bytecode"].get(str(fr["code"]), [])}
            ops = s.get("ops")
            steps.append({
                "ln": s["ln"],
                "file": fi,
                "src": lines[fi][s["ln"] - 1] if s["ln"] else None,
                "f": s["f"],
                "frame": {"name": fr["func"], "file": fr.get("file"),
                          "parent": fr["parent"]},
                "u": s["u"],
                "synth": code.get("synth"),
                "ops": [{"off": o, "op": bc[o][1], "arg": bc[o][2]}
                        for o in ops] if ops else None,
            })
        out[run["call"]] = steps
    files = [{"path": p, "lines": ls} for p, ls in zip(paths, lines)]
    return {"files": files, "dis": dis, "runs": out}


def blanks(steps):
    """(lege rijen, waarvan synth, stappen zonder regel)."""
    empty = [s for s in steps if s["ops"] is None]
    return (sum(s["u"] for s in empty),
            sum(s["u"] for s in empty if s["synth"]),
            sum(s["ln"] is None for s in steps))


def main():
    src, dst = sys.argv[1:3]
    with open(src, encoding="utf-8") as f:
        runs = json.load(f)
    out = convert(runs)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    for call, steps in out["runs"].items():
        b, syn, noln = blanks(steps)
        print(f"{call}: {len(steps)} stappen, {sum(s['u'] for s in steps)} υ,"
              f" {b} leeg ({syn} synth), {noln} zonder regel")
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
