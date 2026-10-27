.PHONY: up down migrate seed api web test lint build
up:
	docker compose up --build -d
down:
	docker compose down
migrate:
	docker compose exec api alembic upgrade head
seed:
	docker compose exec api python seed.py
api:
	cd apps/api && python -m uvicorn app.main:app --reload --port 8000
web:
	cd apps/web && npm run dev
test:
	cd apps/api && python -m pytest -q
lint:
	cd apps/api && python -m ruff check .
	cd apps/web && npm run lint
build:
	cd apps/web && npm run build
