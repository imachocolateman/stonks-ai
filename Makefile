.PHONY: help install test lint format type-check clean run dev

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Run linting checks"
	@echo "  make format       - Format code with black"
	@echo "  make type-check   - Run type checking with mypy"
	@echo "  make clean        - Clean generated files"
	@echo "  make run          - Run the application"
	@echo "  make dev          - Run in development mode"
	@echo "  make all          - Run format, lint, type-check, and test"

install:
	pip install -r requirements.txt

test:
	pytest

test-verbose:
	pytest -v

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/

lint-fix:
	ruff check --fix src/ tests/

format:
	black src/ tests/

format-check:
	black --check src/ tests/

type-check:
	mypy src/

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

run:
	python -m src.main

dev:
	python -m src.main info

all: format lint type-check test
	@echo "All checks passed!"
