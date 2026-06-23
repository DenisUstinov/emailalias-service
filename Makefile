COMPOSE := docker compose

.PHONY: all clean up down restart test test-path test-cov lint check migrate migrate-new nuke

all: up

clean: down

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart api

test:
	$(COMPOSE) exec -e TESTING=true api uv run pytest -v -p no:xdist

test-path:
	$(COMPOSE) exec -e TESTING=true api uv run pytest -v -p no:xdist $(filter-out $@,$(MAKECMDGOALS))

test-cov:
	$(COMPOSE) exec -e TESTING=true api uv run pytest -v --cov=app --cov-report=term-missing -p no:xdist

lint:
	uv run pre-commit run --all-files

check: lint test-cov

migrate-new:
	@read -p "Message: " msg; \
	$(COMPOSE) exec -T api alembic revision --autogenerate -m "$$msg"

migrate:
	$(COMPOSE) exec -T api alembic upgrade head

nuke:
	@docker compose down -v --remove-orphans || true
	@docker rm -f $$(docker ps -aq) 2>/dev/null || true
	@docker system prune -a --volumes -f
