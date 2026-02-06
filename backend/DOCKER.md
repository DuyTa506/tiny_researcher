# Docker Deployment Guide

## Overview

This guide shows how to deploy the Research Assistant using Docker and Docker Compose for easy one-shot startup.

## Quick Start (One Command)

```bash
# Navigate to the project
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend

# Start everything with one command
docker compose -f docker/docker-compose.yml up -d

# Check status
docker compose -f docker/docker-compose.yml ps

# View logs
docker compose -f docker/docker-compose.yml logs -f api
```

Access the API at: http://localhost:8000/docs

## Architecture

The Docker Compose setup includes:

### Core Services (Always Running)
1. **API** - FastAPI application (port 8000)
2. **MongoDB** - Database (port 27017)
3. **Redis** - Cache and sessions (port 6379)

### Optional Tools (With `--profile tools`)
4. **Mongo Express** - MongoDB web UI (port 8081)
5. **Redis Commander** - Redis web UI (port 8082)

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- `.env` file with API keys

## Setup

### 1. Create .env File

```bash
# Create .env in the backend directory
cat > .env << 'EOF'
# LLM API Keys (at least one required)
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here

# Database (handled by docker-compose, these are defaults)
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=research_assistant

# Cache (handled by docker-compose)
REDIS_URL=redis://localhost:6379/0

# App Settings
ENVIRONMENT=development
PROJECT_NAME="Research Assistant"
VERSION=3.4.0
EOF

# Edit and add your actual API keys
nano .env
```

### 2. Build and Start Services

```bash
# Start all services (API, MongoDB, Redis)
docker compose -f docker/docker-compose.yml up -d

# Or build from scratch
docker compose -f docker/docker-compose.yml up -d --build

# Start with optional tools (MongoDB/Redis web UIs)
docker compose -f docker/docker-compose.yml --profile tools up -d
```

### 3. Verify Services

```bash
# Check running containers
docker compose -f docker/docker-compose.yml ps

# Should show:
# - research_assistant_api (healthy)
# - research_assistant_mongo (healthy)
# - research_assistant_redis (healthy)

# Test the API
curl http://localhost:8000/health
# Should return: {"status":"ok","version":"3.4.0"}
```

## Usage

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| API - Swagger | http://localhost:8000/docs | None |
| API - ReDoc | http://localhost:8000/redoc | None |
| API - Health | http://localhost:8000/health | None |
| Mongo Express | http://localhost:8081 | admin / admin123 |
| Redis Commander | http://localhost:8082 | None |

### Common Commands

```bash
# View logs
docker compose -f docker/docker-compose.yml logs -f

# View specific service logs
docker compose -f docker/docker-compose.yml logs -f api
docker compose -f docker/docker-compose.yml logs -f mongo
docker compose -f docker/docker-compose.yml logs -f redis

# Restart services
docker compose -f docker/docker-compose.yml restart

# Stop services
docker compose -f docker/docker-compose.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker/docker-compose.yml down -v

# Rebuild API after code changes
docker compose -f docker/docker-compose.yml up -d --build api
```

### Development Workflow

The API container has hot-reload enabled via volume mount:

```bash
# Start services
docker compose -f docker/docker-compose.yml up -d

# Edit code in src/
# Changes are automatically reflected (uvicorn --reload)

# View logs to see reload
docker compose -f docker/docker-compose.yml logs -f api
```

## Testing with Docker

### Option 1: Run tests inside container

```bash
# Execute tests in the running API container
docker compose -f docker/docker-compose.yml exec api python scripts/test_api.py

# Or run CLI tests
docker compose -f docker/docker-compose.yml exec api python scripts/test_cli.py
```

### Option 2: Run tests from host

```bash
# Services must be running
docker compose -f docker/docker-compose.yml up -d

# Run tests from host (using services on localhost)
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python scripts/test_api.py
```

## Production Deployment

### 1. Enable MongoDB Authentication

Edit `docker/docker-compose.yml`:

```yaml
mongo:
  environment:
    - MONGO_INITDB_ROOT_USERNAME=admin
    - MONGO_INITDB_ROOT_PASSWORD=your_secure_password
    - MONGO_INITDB_DATABASE=research_assistant
```

Update API environment:
```yaml
api:
  environment:
    - MONGO_URL=mongodb://admin:your_secure_password@mongo:27017
```

### 2. Enable Redis Password

Edit `docker/docker-compose.yml`:

```yaml
redis:
  command: redis-server --appendonly yes --requirepass your_redis_password
```

Update API environment:
```yaml
api:
  environment:
    - REDIS_URL=redis://:your_redis_password@redis:6379/0
```

### 3. Use Docker Secrets

```yaml
api:
  secrets:
    - openai_api_key
    - gemini_api_key

secrets:
  openai_api_key:
    file: ./secrets/openai_key.txt
  gemini_api_key:
    file: ./secrets/gemini_key.txt
```

### 4. Production Compose Override

Create `docker/docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  api:
    restart: always
    environment:
      - ENVIRONMENT=production
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

  mongo:
    restart: always

  redis:
    restart: always
```

Deploy:
```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d
```

## Monitoring

### Health Checks

All services have health checks configured:

```bash
# Check health status
docker compose -f docker/docker-compose.yml ps

# View health check logs
docker inspect research_assistant_api | jq '.[0].State.Health'
```

### Resource Usage

```bash
# View resource usage
docker stats

# View specific container
docker stats research_assistant_api
```

### Logs Management

```bash
# Follow logs with timestamps
docker compose -f docker/docker-compose.yml logs -f -t

# Last 100 lines
docker compose -f docker/docker-compose.yml logs --tail=100

# Since specific time
docker compose -f docker/docker-compose.yml logs --since 2h

# Filter by service
docker compose -f docker/docker-compose.yml logs -f api mongo redis
```

## Data Persistence

### Volumes

Data is persisted in Docker volumes:

```bash
# List volumes
docker volume ls | grep research

# Inspect volume
docker volume inspect backend_mongo_data

# Backup MongoDB data
docker run --rm \
  -v backend_mongo_data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/mongo-backup-$(date +%Y%m%d).tar.gz -C /data .

# Restore MongoDB data
docker run --rm \
  -v backend_mongo_data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar xzf /backup/mongo-backup-20260206.tar.gz -C /data
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker compose -f docker/docker-compose.yml logs

# Check port conflicts
lsof -i :8000
lsof -i :27017
lsof -i :6379

# Remove all containers and start fresh
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml up -d --build
```

### API container unhealthy

```bash
# Check logs
docker compose -f docker/docker-compose.yml logs api

# Check if MongoDB/Redis are healthy
docker compose -f docker/docker-compose.yml ps

# Restart API
docker compose -f docker/docker-compose.yml restart api
```

### Can't connect to MongoDB from host

```bash
# MongoDB is accessible on localhost:27017
mongosh mongodb://localhost:27017/research_assistant

# Or use Docker
docker compose -f docker/docker-compose.yml exec mongo mongosh
```

### Redis connection issues

```bash
# Test Redis from host
redis-cli ping

# Or use Docker
docker compose -f docker/docker-compose.yml exec redis redis-cli ping
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | `research_assistant` | Database name |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `OPENAI_API_KEY` | - | OpenAI API key (required) |
| `GEMINI_API_KEY` | - | Gemini API key (optional) |
| `ENVIRONMENT` | `development` | Environment (development/production) |
| `PROJECT_NAME` | `Research Assistant` | Project name |
| `VERSION` | `3.4.0` | Application version |

## Makefile Shortcuts (Optional)

Create a `Makefile` in the backend directory:

```makefile
.PHONY: up down logs build restart clean test

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

logs:
	docker compose -f docker/docker-compose.yml logs -f

build:
	docker compose -f docker/docker-compose.yml up -d --build

restart:
	docker compose -f docker/docker-compose.yml restart

clean:
	docker compose -f docker/docker-compose.yml down -v

test:
	docker compose -f docker/docker-compose.yml exec api python scripts/test_api.py

tools:
	docker compose -f docker/docker-compose.yml --profile tools up -d
```

Usage:
```bash
make up      # Start services
make logs    # View logs
make down    # Stop services
make clean   # Stop and remove volumes
make test    # Run tests
make tools   # Start with web UIs
```

## Summary

### One-Shot Start
```bash
cd backend
docker compose -f docker/docker-compose.yml up -d
```

### Access
- API: http://localhost:8000/docs
- MongoDB: localhost:27017
- Redis: localhost:6379

### Stop
```bash
docker compose -f docker/docker-compose.yml down
```

---
**Version:** v3.4
**Status:** ✅ Production Ready
**Updated:** 2026-02-06
