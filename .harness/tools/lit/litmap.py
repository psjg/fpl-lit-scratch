"""Rewrite <tangled>:<line> in any tool's text output to <page.md>:<line>."""
import json, re, sys
from pathlib import Path
maps = {}
for m in Path(sys.argv[1]).rglob("*.map.json"):
    py = str(m)[: -len(".map.json")]
    maps[py] = {t: (pg, ml, col) for t, pg, ml, col in json.loads(m.read_text())}
pat = re.compile("(" + "|".join(re.escape(k) for k in maps) + r")(:|\", line )(\d+)(?::(\d+))?")
def sub(m):
    hit = maps[m[1]].get(int(m[3]))
    if not hit: return m[0]
    pg, ml, col = hit
    c = f":{int(m[4]) - col}" if m[4] else ""
    return f"{pg}:{ml}{c} [{m[1]}:{m[3]}]"
for line in sys.stdin: sys.stdout.write(pat.sub(sub, line))
