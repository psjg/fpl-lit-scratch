"""
# 01.01.07 Seed

The tangled tree has no REPL or session kernel of its own yet: they are
the seed walker's, [`repl`](../fpl/repl.py) and
[`kernel`](../fpl/kernel.py). The seed cannot be imported beside this
package, since both are named `fpl`, so a command that needs one runs it
as a child process whose path puts the seed's root first. The wheel
carries the seed as `fpl/_seed/fpl` (`pyproject.toml`); a checkout has
it in `01-bootstrap/` (TD-0014). [01.01.06-cli](01.01.06-cli.md) starts
the REPL this way, and [01.01.08-pty](01.01.08-pty.md) the kernel.

Where the seed walker is, and a command to run one of its modules.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = (HERE / "_seed", HERE.parents[1])
"""
Where the seed walker's root may be, in order: beside this module, as
the wheel installs it, or the checkout's 01-bootstrap/.
"""


def command(module: str) -> tuple[list[str], dict[str, str]]:
    """
    The argv and environment that run the seed's `module` (`fpl.repl`).

    The path is the seed's root, then this process's own, so `fpl` is the
    seed and lark and the rest are found where they were; PYTHONSAFEPATH
    keeps the working directory off it. Refused (LookupError): no seed
    in any of SEEDS, the message naming where it looked.
    """
    leaf = Path(*module.split(".")).with_suffix(".py")
    found = [root for root in SEEDS if (root / leaf).is_file()]
    if not found:
        raise LookupError(" or ".join(str(root / leaf) for root in SEEDS))
    path = os.pathsep.join([str(found[0]), *filter(None, sys.path)])
    env = os.environ | {"PYTHONPATH": path, "PYTHONSAFEPATH": "1"}
    return [sys.executable, "-m", module], env
