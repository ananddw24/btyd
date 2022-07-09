.PHONY: init lint check_lint test

init:
	poetry install
	poetry shell

lint:
	poetry isort .
	poetry black .

check_lint:
	flake8 .
	isort --check-only .
	black --diff --check --fast .

test:
	pytest