
SHELL 	:= /bin/bash

bump-patch:
	sh admin/admin-commands.sh --cmd bump --level patch
bump-minor:
	sh admin/admin-commands.sh --cmd bump --level minor
bump-major:
	sh admin/admin-commands.sh --cmd bump --level major
pull:
	sh admin/admin-commands.sh --cmd pull
push:
	sh admin/admin-commands.sh --cmd push
install:
	# First-time install - use when lock file is stable
	poetry install -v
update:
	# Update lock file based on changed reqs
	poetry update -v
lock:
	# Refresh the poetry lock file
	poetry lock
exp-reqs:
    # Exports the current poetry env to requirements.frozen
	poetry export -f requirements.txt > requirements.frozen
check:
	pre-commit run --all-files
install-dev:
	poetry install --all-groups
	pre-commit install
test:
	tox
rebuild-test:
	tox --recreate -e py312
