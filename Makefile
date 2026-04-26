COMPOSE = docker compose -f docker/docker-compose.yml

.PHONY: help test test-cov lint format run up down logs build restart shell

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

test: ## Run test suite
	source .venv/bin/activate && python -m pytest garmin_coach/tests/ -v

test-cov: ## Run tests with coverage report
	source .venv/bin/activate && python -m pytest garmin_coach/tests/ -v --cov=garmin_coach --cov-report=term-missing

lint: ## Lint with ruff
	source .venv/bin/activate && ruff check .

format: ## Format with ruff
	source .venv/bin/activate && ruff format .

run: ## Run locally (requires .env)
	source .venv/bin/activate && python main.py

up: ## Start Docker (detached)
	$(COMPOSE) up -d

build: ## Build Docker image
	$(COMPOSE) build

up-build: ## Build and start Docker (detached)
	$(COMPOSE) up -d --build

down: ## Stop Docker
	$(COMPOSE) down

hard-restart: down up-build ## Stop, build, and start Docker

logs: ## Follow Docker logs
	$(COMPOSE) logs -f

restart: ## Restart Docker service
	$(COMPOSE) restart garmin-coach

shell: ## Open shell in running container
	$(COMPOSE) exec garmin-coach bash
