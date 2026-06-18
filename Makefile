.PHONY: help db-up db-down db-logs api-install api-migrate api-test api-lint api-format api-format-check api-dev web-install web-lint web-build web-dev verify

help:
	@echo "Eidolon commands"
	@echo "  make db-up       Start local PostgreSQL"
	@echo "  make api-migrate Run backend migrations"
	@echo "  make api-test    Run backend tests"
	@echo "  make api-lint    Run backend lint"
	@echo "  make api-dev     Start FastAPI"
	@echo "  make web-dev     Start Next.js"
	@echo "  make verify      Run available checks"

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

api-install:
	cd apps/api && pip install -e ".[dev]"

api-migrate:
	cd apps/api && alembic upgrade head

api-test:
	cd apps/api && pytest

api-lint:
	cd apps/api && ruff check .

api-format:
	cd apps/api && ruff format .

api-format-check:
	cd apps/api && ruff format --check .

api-dev:
	cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

web-install:
	cd apps/web && npm install

web-lint:
	cd apps/web && npm run lint

web-build:
	cd apps/web && npm run build

web-dev:
	cd apps/web && npm run dev

verify:
	$(MAKE) api-migrate
	$(MAKE) api-test
	$(MAKE) api-lint
	$(MAKE) api-format-check
	$(MAKE) web-lint
	$(MAKE) web-build
