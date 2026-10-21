import ast, sys
from collections import Counter
def stmts(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return [ast.dump(s) for s in tree.body]
a, b = stmts(sys.argv[1]), stmts(sys.argv[2])
print("top-level statements:", len(a), len(b))
print("multiset equal:", Counter(a) == Counter(b))
print("order equal:", a == b)
