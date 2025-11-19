.PHONY: help install install-dev test lint format clean docker-build docker-up docker-down run

help:  ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -e .

install-dev:  ## Install development dependencies
	pip install -e ".[dev]"
	pre-commit install

test:  ## Run tests with coverage
	pytest tests/ -v --cov=src/auto_pm_agent_api --cov-report=html --cov-report=term

test-fast:  ## Run tests without coverage
	pytest tests/ -v

lint:  ## Run linters
	ruff check src/ tests/
	mypy src/

format:  ## Format code with black and ruff
	black src/ tests/
	ruff check --fix src/ tests/

clean:  ## Clean up cache and build files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov dist build

docker-build:  ## Build Docker image
	docker-compose build

docker-up:  ## Start Docker containers
	docker-compose up -d

docker-down:  ## Stop Docker containers
	docker-compose down

docker-logs:  ## Show Docker logs
	docker-compose logs -f api

run:  ## Run the application locally
	uvicorn auto_pm_agent_api.infrastructure.api.main:app --reload --host 0.0.0.0 --port 8000

run-prod:  ## Run the application in production mode
	uvicorn auto_pm_agent_api.infrastructure.api.main:app --host 0.0.0.0 --port 8000 --workers 4
