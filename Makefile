.PHONY: test

# Run tests: failed first (if any), then all others
test:
	uv run pytest --ff tests/
