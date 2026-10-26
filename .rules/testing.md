# testing.md — Testing Nested Rules

Applies when writing or modifying tests.

- Prefer the project's existing test framework, fixtures, and helpers.
- Each test asserts one behavior and is independent of execution order.
- Bug fixes include a regression test that fails without the fix.
- Do not skip, xfail, delete, or loosen tests to make a suite pass.
- Use deterministic data; avoid dependence on clock, randomness, or network unless controlled.
- Keep tests readable: descriptive names and minimal setup.
- Use property-based tests only where they add genuine coverage and the tooling exists.
- Integration tests that require services must be runnable via the documented command.
- Report which tests were run and their results; never claim a pass not observed.