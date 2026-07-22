COMPOSE := docker compose -f docker-compose.yml -f docker-compose.dev.yml

LOADTEST_TARGET_URL ?= http://192.168.0.101

.PHONY: all clean up down restart logs loadtest-path test test-path test-cov lint check migrate migrate-new nuke

all: up

clean: down

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart api

logs:
	$(COMPOSE) logs -f

loadtest-path:
	docker run --rm -i \
		-v $(PWD):/project \
		-w /project \
		-e LOADTEST_TARGET_URL=$(LOADTEST_TARGET_URL) \
		grafana/k6:latest run $(filter-out $@,$(MAKECMDGOALS))

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
