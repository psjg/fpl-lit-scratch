"""Bootstrap implementation of FPL, in Python.

:func:`fpl.driver.run` takes a program through :mod:`fpl.parse`,
:mod:`fpl.desugar`, :mod:`fpl.types` and :mod:`fpl.eval`, and
:mod:`fpl.print` renders the result. :func:`fpl.__main__.main` is the
command line. The package layout is in ``.agents/CONVENTIONS.md`` and
the stack in ``.agents/STACK.md``.
"""
