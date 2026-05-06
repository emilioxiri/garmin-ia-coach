---
name: pytest-cov-gate
description: Run pytest with coverage and verify the project's 85% coverage gate before commit. Use when the user asks to test, check coverage, validate before commit, or invokes /pytest-cov-gate.
disable-model-invocation: true
---

# pytest-cov-gate

Validate that the test suite passes and total coverage meets the project gate
defined in `pyproject.toml` (`[tool.coverage.report] fail_under = 85`).

## Steps

1. Activate venv if present:
   ```bash
   source .venv/bin/activate 2>/dev/null || true
   ```
2. Run the suite with coverage:
   ```bash
   python -m pytest garmin_coach/tests/ -v \
     --cov=garmin_coach --cov-report=term-missing
   ```
3. Read the `TOTAL` line from the coverage report.
4. Report:
   - PASS/FAIL of the test suite.
   - Total coverage % vs gate (85%).
   - If below gate: list the top 3 files by missing lines so the user knows
     where to add tests.
5. If any test failed, do not run further work — surface the failing test name
   and short traceback excerpt.

## Notes

- Coverage scope excludes `garmin_coach/bot.py`, `main.py`, and the test
  package per `[tool.coverage.run] omit`.
- This is a user-only skill: run it on demand, do not auto-invoke.
