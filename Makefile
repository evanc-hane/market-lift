.PHONY: install simulate warehouse analyze demo dashboard test lint typecheck package check

install:
	python -m pip install -e ".[dev]"

simulate:
	marketlift-simulate --scale demo

warehouse:
	marketlift-build

analyze:
	marketlift-analyze

demo:
	marketlift-run --scale demo

dashboard:
	streamlit run dashboard/app.py

test:
	pytest --cov=marketlift --cov-report=term-missing --cov-fail-under=80

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy

package:
	python -m build

check: lint typecheck test package

