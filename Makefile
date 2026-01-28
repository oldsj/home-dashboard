.PHONY: test deploy

# Pi deployment config (override with: make deploy PI_HOST=my-pi)
PI_HOST ?= office-dashboard
PI_PATH ?= ~/dashboard

# Optimized test target: parallel execution, failed first, stop on first failure
test:
	uv run pytest -n auto --ff -x tests/

# Deploy code to Pi (./run watches for changes and auto-reloads)
deploy:
	@echo "Deploying to $(PI_HOST):$(PI_PATH)..."
	rsync -avz --delete \
		--exclude='.git' \
		--exclude='.venv' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		--exclude='.pytest_cache' \
		--exclude='.trunk' \
		--exclude='node_modules' \
		--exclude='.planning' \
		./ $(PI_HOST):$(PI_PATH)/
	@echo "Done! http://$(PI_HOST):9753"
