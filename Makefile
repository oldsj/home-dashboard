.PHONY: test deploy release

# Pi deployment config (override with: make deploy PI_HOST=my-pi)
PI_HOST ?= office-dashboard
PI_PATH ?= ~/dashboard

# Optimized test target: parallel execution, failed first, stop on first failure
test:
	uv run pytest -n auto --ff -x tests/

# Deploy to Pi: push to dev branch and trigger pull
deploy:
	git push origin dev
	ssh $(PI_HOST) "cd $(PI_PATH) && git pull"
	@echo "Deployed! http://$(PI_HOST):9753"

# Release to production: squash merge dev into main, then rebase dev
release:
	git checkout main
	git pull origin main
	git merge --squash dev
	git commit -m "Release: $$(git log main..dev --oneline | wc -l | tr -d ' ') commits from dev"
	git push origin main
	git checkout dev
	git rebase main
	git push -f origin dev
