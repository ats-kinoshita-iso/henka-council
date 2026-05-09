# Hello-World CLI — Product Specification

This is a trivial hello-world command-line tool used as a structural fixture for
trine-eval acceptance tests. The tool accepts an optional `--name` argument and
prints a greeting to stdout.

Sprint 1 ships the core `hello()` function in `src/hello.py`. Sprint 2 adds a
single-assertion test in `tests/test_hello.py` to verify the greeting output.
No external dependencies are required; the implementation is pure Python.
