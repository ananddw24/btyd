.PHONY: init lint check_lint test

init:
	poetry install

lint:
	poetry run isort .
	poetry run black .

check_lint:
	poetry run flake8 .
	poetry run isort --check-only .
	poetry run black --diff --check --fast .

test:
	poetry run pytest