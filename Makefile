.PHONY: test

# Optimized test target: parallel execution, failed first, stop on first failure
test:
	uv run pytest -n auto --ff -x tests/
