.PHONY: help up down logs build restart clean test tools api-test cli-test services services-down services-ui services-full

help:
	@echo "Research Assistant - Docker Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Full Stack (API + Services):"
	@echo "  up          Start all services + API"
	@echo "  down        Stop all services + API"
	@echo "  logs        View logs (all)"
	@echo "  build       Rebuild and start"
	@echo "  restart     Restart all"
	@echo "  clean       Stop and remove volumes"
	@echo ""
	@echo "Services Only (for local development):"
	@echo "  services         Start MongoDB + Redis only"
	@echo "  services-ui      Start services + web UIs"
	@echo "  services-full    Start all services (MongoDB, Redis, Qdrant, Elasticsearch)"
	@echo "  services-down    Stop all services"
	@echo ""
	@echo "Testing:"
	@echo "  test        Run API tests"
	@echo "  api-test    Run API tests"
	@echo "  cli-test    Run CLI tests"
	@echo ""
	@echo "Other:"
	@echo "  tools       Start with web UI tools"
	@echo "  ps          Show service status"
	@echo "  health      Check API health"

# Full stack commands
up:
	docker compose -f docker/docker-compose.yml up -d
	@echo "✅ Full stack started (API + Services)"
	@echo "API: http://localhost:8000/docs"

down:
	docker compose -f docker/docker-compose.yml down
	@echo "✅ Full stack stopped"

# Services only commands (for local development)
services:
	docker compose -f docker/docker-compose.services.yml up -d
	@echo "✅ Services started (MongoDB + Redis)"
	@echo "MongoDB: localhost:27017"
	@echo "Redis: localhost:6379"
	@echo ""
	@echo "Now run your app locally:"
	@echo "  source .venv/bin/activate"
	@echo "  export \$$(grep -v '^#' .env | xargs)"
	@echo "  python research_cli.py"
	@echo "  # OR"
	@echo "  uvicorn src.api.main:app --reload"

services-ui:
	docker compose -f docker/docker-compose.services.yml --profile ui up -d
	@echo "✅ Services started with web UIs"
	@echo "MongoDB: localhost:27017"
	@echo "Redis: localhost:6379"
	@echo "MongoDB UI: http://localhost:8081 (admin/admin123)"
	@echo "Redis UI: http://localhost:8082"

services-full:
	docker compose -f docker/docker-compose.services.yml --profile full --profile ui up -d
	@echo "✅ All services started"
	@echo "MongoDB: localhost:27017"
	@echo "Redis: localhost:6379"
	@echo "Qdrant: localhost:6333"
	@echo "Elasticsearch: localhost:9200"
	@echo "MongoDB UI: http://localhost:8081"
	@echo "Redis UI: http://localhost:8082"

services-down:
	docker compose -f docker/docker-compose.services.yml down
	@echo "✅ Services stopped"

logs:
	docker compose -f docker/docker-compose.yml logs -f

logs-services:
	docker compose -f docker/docker-compose.services.yml logs -f

build:
	docker compose -f docker/docker-compose.yml up -d --build
	@echo "✅ Services rebuilt and started"

restart:
	docker compose -f docker/docker-compose.yml restart
	@echo "✅ Services restarted"

clean:
	docker compose -f docker/docker-compose.yml down -v
	docker compose -f docker/docker-compose.services.yml down -v
	@echo "✅ All services stopped and volumes removed"

test: api-test

tools:
	docker compose -f docker/docker-compose.yml --profile tools up -d
	@echo "✅ Services started with web UI tools"
	@echo "API: http://localhost:8000/docs"
	@echo "MongoDB UI: http://localhost:8081 (admin/admin123)"
	@echo "Redis UI: http://localhost:8082"

api-test:
	docker compose -f docker/docker-compose.yml exec api python scripts/test_api.py

cli-test:
	docker compose -f docker/docker-compose.yml exec api python scripts/test_cli.py

ps:
	docker compose -f docker/docker-compose.yml ps

health:
	@echo "Checking health..."
	@curl -f http://localhost:8000/health || echo "❌ API not healthy"
