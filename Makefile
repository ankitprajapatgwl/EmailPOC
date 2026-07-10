.DEFAULT_GOAL := up
.PHONY: up down restart build logs ps migrate reset-db clean

# One command to run the whole project: builds the images, starts Postgres
# + the app, and the app's entrypoint applies database migrations
# automatically (safe to run every time — see docker/entrypoint.sh).
up:
	@if [ ! -f .env ]; then \
		cp .env.docker.example .env; \
		echo ""; \
		echo "==> Created .env from .env.docker.example."; \
		echo "==> Open .env and fill in: SECRET_KEY, INBOUND_DOMAIN, FROM_EMAIL,"; \
		echo "==> ENGAGELAB_API_USER, ENGAGELAB_API_KEY — then run 'make up' again."; \
		echo ""; \
		exit 1; \
	fi
	docker compose up -d --build
	@echo ""
	@echo "EmailPOC is starting. Give it a few seconds, then open:"
	@echo "  http://localhost:$$(grep -m1 '^APP_PORT=' .env | cut -d= -f2)"
	@echo "Follow logs with: make logs"

down:
	docker compose down

restart:
	docker compose restart

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

ps:
	docker compose ps

# Re-run migrations by hand (the app container already does this on every
# start; this is only useful for troubleshooting).
migrate:
	docker compose exec app alembic upgrade head

# Wipe the database volume too — the next 'make up' starts from an empty DB.
reset-db:
	docker compose down -v

clean: down
	docker image prune -f
