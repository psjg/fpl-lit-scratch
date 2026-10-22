"""
The graph of a composition, read as data from the tangled tree.

Each check runs in a child interpreter over `python/fpl`
(tests/lit.py). The graph is built from the passes alone: no check
here runs a pass.
"""

from lit import lit

EXPLAIN = (
    "Source -> lex -> Tokens -> parse -> Syntax -> desugar -> Core"
    " -> elaborate -> Core -> eval -> Stacks"
)


def out(code: str) -> str:
    """
    Run `code` in the tangled tree; its stdout, the exit status checked.
    """
    done = lit(code)
    assert done.returncode == 0, done.stderr.decode()
    return done.stdout.decode()


def test_explain_names_the_chain() -> None:
    code = (
        "from fpl.graph import explain\n"
        "from fpl.run import run_now\n"
        "print(explain(run_now))\n"
    )
    assert out(code) == EXPLAIN + "\n"


def test_run_now_has_a_node_per_stage_and_two_ports() -> None:
    code = (
        "from fpl.graph import graph_of\n"
        "from fpl.run import run_now\n"
        "g = graph_of(run_now)\n"
        "print(len(run_now.stages), len(g.nodes), len(g.edges))\n"
        "print(g.nodes[0].name, g.nodes[-1].name)\n"
    )
    assert out(code) == "5 7 6\nc.source c.target\n"


def test_a_single_pass_has_three_nodes_and_two_edges() -> None:
    code = (
        "from fpl.graph import graph_of\n"
        "from fpl.lex import lex\n"
        "g = graph_of(lex)\n"
        "print(len(g.nodes), len(g.edges))\n"
        "print([(e.source, e.target, e.repr) for e in g.edges])\n"
    )
    assert out(code) == ("3 2\n[(0, 1, 'Source'), (1, 2, 'Tokens')]\n")


def test_a_core_to_core_pass_has_no_self_loop() -> None:
    code = (
        "from fpl.graph import graph_of\n"
        "from fpl.elaborate import elaborate\n"
        "g = graph_of(elaborate)\n"
        "print(len(g.nodes), len(g.edges))\n"
    )
    assert out(code) == "3 2\n"


def test_dot_is_graphviz() -> None:
    code = (
        "from fpl.graph import dot\n"
        "from fpl.run import run_now\n"
        "print(dot(run_now))\n"
    )
    text = out(code)
    assert text.startswith("digraph")
    assert text.count("->") == 6


def test_mermaid_is_a_left_to_right_flowchart() -> None:
    code = (
        "from fpl.graph import mermaid\n"
        "from fpl.run import run_now\n"
        "print(mermaid(run_now))\n"
    )
    text = out(code)
    assert text.startswith("flowchart LR")
    assert text.count("-->") == 6


def test_a_nested_composition_is_the_same_graph() -> None:
    code = (
        "from fpl.arrow import pass_compose\n"
        "from fpl.graph import graph_of\n"
        "from fpl.lex import lex\n"
        "from fpl.parse import parse\n"
        "from fpl.desugar import desugar\n"
        "a = graph_of((lex >> parse) >> desugar)\n"
        "b = graph_of(lex >> (parse >> desugar))\n"
        "print(a == b)\n"
    )
    assert out(code) == "True\n"


def test_labels_are_escaped_for_dot_and_mermaid() -> None:
    """
    A pass or representation name with a quote, a backslash or a pipe
    must not end the label that holds it.
    """
    code = (
        "from fpl.arrow import Pass\n"
        "from fpl.graph import dot, mermaid\n"
        "p = Pass('a\"b\\\\c', str, 'B|C', 'D\"E')\n"
        "print(dot(p))\n"
        "print(mermaid(p))\n"
    )
    text = out(code)
    assert 'label="a\\"b\\\\c"' in text
    assert 'label="B|C"' in text
    assert 'label="D\\"E"' in text
    assert '["a#quot;b\\c"]' in text
    assert "-->|B#124;C|" in text
    assert "-->|D#quot;E|" in text
