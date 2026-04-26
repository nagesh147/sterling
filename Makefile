.PHONY: backend frontend test test-v lint docker-up docker-down docker-logs clean

backend:
	cd backend && .venv/bin/uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest tests/ -q

test-v:
	cd backend && .venv/bin/pytest tests/ -v

lint:
	cd backend && .venv/bin/python -m py_compile app/**/*.py && echo "OK"

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

setup-backend:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

setup-frontend:
	cd frontend && npm install

setup: setup-backend setup-frontend

clean:
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -name "*.pyc" -delete 2>/dev/null || true
	rm -f backend/sterling_paper.db
