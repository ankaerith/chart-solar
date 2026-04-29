.PHONY: dev api web worker test lint typecheck build clean

dev:
	docker compose up

api:
	uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run python -m backend.workers.forecast_worker

web:
	cd frontend && bun run dev

test:
	uv run pytest

lint:
	uv run ruff check
	cd frontend && bun run lint

typecheck:
	cd frontend && bun run typecheck

build:
	docker compose build

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache frontend/.next frontend/node_modules
