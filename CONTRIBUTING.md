# Contributing to MarketLift

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
make check
```

Keep changes focused and include tests for behavioral changes. The simulator must remain
deterministic for a fixed seed, and analysis code must never use the hidden ground-truth table
when estimating effects.

## Pull request checklist

- Explain the business or statistical behavior being changed.
- Add or update automated tests.
- Run linting, formatting, type checks, and the test suite.
- Update the experiment design or metric contract when assumptions change.
- Do not commit generated DuckDB files or real customer, courier, or marketplace data.

