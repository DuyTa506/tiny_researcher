# Local Development Guide

## Quick Start - Services Only

Run infrastructure (MongoDB, Redis) in Docker, but run your app locally for easier debugging.

### 1. Start Services

```bash
# Start MongoDB + Redis only
make services

# Or with web UIs
make services-ui

# Or with all services (including Qdrant, Elasticsearch)
make services-full
```

### 2. Run Your App Locally

**Option A: CLI Mode**
```bash
# Activate venv
source .venv/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Run CLI
python research_cli.py
```

**Option B: API Mode**
```bash
# Activate venv
source .venv/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Run API with hot-reload
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Access

- **API Docs**: http://localhost:8000/docs
- **MongoDB**: localhost:27017
- **Redis**: localhost:6379
- **MongoDB UI** (if started with `services-ui`): http://localhost:8081
- **Redis UI** (if started with `services-ui`): http://localhost:8082

### 4. Stop Services

```bash
make services-down
```

## Available Services

### Basic Services (default)
```bash
make services
```
Starts:
- ✅ MongoDB (port 27017)
- ✅ Redis (port 6379)

### With Web UIs
```bash
make services-ui
```
Starts:
- ✅ MongoDB (port 27017)
- ✅ Redis (port 6379)
- ✅ MongoDB Express (port 8081) - Web UI
- ✅ Redis Commander (port 8082) - Web UI

### All Services
```bash
make services-full
```
Starts:
- ✅ MongoDB (port 27017)
- ✅ Redis (port 6379)
- ✅ Qdrant (port 6333) - Vector database
- ✅ Elasticsearch (port 9200) - Full-text search
- ✅ MongoDB Express (port 8081)
- ✅ Redis Commander (port 8082)

## Complete Workflow Example

### Research with CLI

```bash
# 1. Start services
make services

# 2. Activate environment
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# 3. Run CLI
python research_cli.py

# Use the CLI
You: transformer models
Agent: [Creates research plan...]
You: yes
[Pipeline runs, using Docker MongoDB/Redis]

# 4. When done, stop services
make services-down
```

### API Development

```bash
# 1. Start services with UIs (for debugging)
make services-ui

# 2. In another terminal, run API
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn src.api.main:app --reload

# 3. Access
# - API: http://localhost:8000/docs
# - MongoDB UI: http://localhost:8081
# - Redis UI: http://localhost:8082

# 4. Make code changes - API auto-reloads

# 5. When done
make services-down
```

## Debugging Tips

### View Service Logs

```bash
# All services
make logs-services

# Specific service
docker logs research_mongo -f
docker logs research_redis -f
```

### Check Service Status

```bash
docker ps | grep research

# Or
docker compose -f docker/docker-compose.services.yml ps
```

### Connect to Services

```bash
# MongoDB
mongosh mongodb://localhost:27017/research_assistant

# Or via Docker
docker exec -it research_mongo mongosh

# Redis
redis-cli

# Or via Docker
docker exec -it research_redis redis-cli
```

### Inspect Data

**MongoDB:**
```bash
# Via web UI
open http://localhost:8081

# Via CLI
mongosh mongodb://localhost:27017/research_assistant
> db.papers.find().limit(5)
> db.conversations.find().limit(5)
```

**Redis:**
```bash
# Via web UI
open http://localhost:8082

# Via CLI
redis-cli
> KEYS *
> GET conversation:abc123
```

## Advantages of Local Development

### ✅ Pros
- **Faster iteration** - No Docker build needed
- **Easy debugging** - Use your IDE debugger
- **Hot reload** - Changes reflect immediately
- **Direct access** - Inspect code, add print statements
- **Lightweight** - Only infrastructure in Docker

### ⚠️ When to Use Full Docker
- Testing production setup
- Deploying to server
- Sharing with team (guaranteed same environment)
- Running multiple instances

## Makefile Commands Summary

### Services Only
```bash
make services        # Start MongoDB + Redis
make services-ui     # + Web UIs
make services-full   # + Qdrant + Elasticsearch
make services-down   # Stop all services
make logs-services   # View logs
```

### Full Stack (API in Docker)
```bash
make up              # Start everything in Docker
make down            # Stop everything
make logs            # View all logs
```

### Testing
```bash
make test            # Run API tests
make api-test        # Run API tests
make cli-test        # Run CLI tests
```

### Cleanup
```bash
make clean           # Remove all containers and volumes
```

## Connection Strings

When running locally, use these connection strings in your `.env`:

```bash
# For local app connecting to Docker services
MONGO_URL=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379/0

# For Qdrant (if using services-full)
QDRANT_URL=http://localhost:6333

# For Elasticsearch (if using services-full)
ELASTICSEARCH_URL=http://localhost:9200
```

## Troubleshooting

### "Can't connect to MongoDB"

```bash
# Check if MongoDB is running
docker ps | grep mongo

# If not, start it
make services

# Check logs
docker logs research_mongo
```

### "Can't connect to Redis"

```bash
# Check if Redis is running
docker ps | grep redis

# If not, start it
make services

# Test connection
redis-cli ping
# Should return: PONG
```

### "Port already in use"

```bash
# Find what's using the port
lsof -i :27017
lsof -i :6379

# Stop the conflicting service
# Then start Docker services
make services
```

### "Qdrant storage locked"

This happens when running CLI and API simultaneously (both try to use embedded Qdrant).

**Solution:**
```bash
# Use Qdrant server mode instead
make services-full

# Update your code to use server mode (localhost:6333)
# instead of embedded mode
```

## Performance Tips

### Keep Services Running

Instead of stopping/starting services frequently:

```bash
# Start services once
make services-ui

# Leave them running all day
# Just restart your app as needed

# At end of day
make services-down
```

### Use Web UIs for Development

```bash
# Always use services-ui during development
make services-ui

# Monitor data in real-time:
# - MongoDB: http://localhost:8081
# - Redis: http://localhost:8082
```

## Example Session

```bash
# Morning: Start services
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend
make services-ui

# Open MongoDB UI in browser
open http://localhost:8081

# Start coding
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# Work on CLI
python research_cli.py
# Test changes...

# Switch to API development
uvicorn src.api.main:app --reload
# Edit code, test, repeat...

# Evening: Stop services
make services-down
```

---
**Recommended for:** Daily development, debugging, testing
**Updated:** 2026-02-06
