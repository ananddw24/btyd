.PHONY: init lint check_lint test

init:
	poetry install

lint:
	poetry isort .
	poetry black .

check_lint:
	poetry flake8 .
	poetry isort --check-only .
	poetry black --diff --check --fast .

test:
	poetry pytest