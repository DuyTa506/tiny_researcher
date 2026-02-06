# Quick Reference - Test From Scratch

## ✅ All Docker Containers Stopped and Cleaned

Ready for fresh testing!

## 🚀 Test Scenarios

### Scenario 1: Services Only + Local App (Recommended for Development)

```bash
# 1. Start infrastructure services
cd /home/duy/Downloads/duy_dev/tiny_researcher/backend
docker compose -f docker/docker-compose.services.yml up -d

# 2. Wait for services to be healthy (10-15 seconds)
sleep 10

# 3. Verify services are running
docker ps | grep research
# Should show: research_mongo and research_redis

# 4. Test MongoDB
docker exec research_mongo mongosh --eval "db.version()"
# Should return: 7.0.29

# 5. Test Redis
docker exec research_redis redis-cli ping
# Should return: PONG

# 6. Run your app locally
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# Option A: CLI
python research_cli.py

# Option B: API
uvicorn src.api.main:app --reload

# 7. When done, stop services
docker compose -f docker/docker-compose.services.yml down
```

### Scenario 2: Services + Web UIs (Best for Debugging)

```bash
# 1. Start services with web UIs
docker compose -f docker/docker-compose.services.yml --profile ui up -d

# 2. Access web UIs
# MongoDB: http://localhost:8081 (admin/admin123)
# Redis: http://localhost:8082

# 3. Run your app locally
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python research_cli.py

# 4. Monitor data in web UIs while your app runs

# 5. Stop
docker compose -f docker/docker-compose.services.yml down
```

### Scenario 3: Full Stack in Docker

```bash
# 1. Start everything (API + Services)
docker compose -f docker/docker-compose.yml up -d

# 2. Access API
# Swagger: http://localhost:8000/docs
# Health: http://localhost:8000/health

# 3. Test
curl http://localhost:8000/health

# 4. View logs
docker compose -f docker/docker-compose.yml logs -f api

# 5. Stop
docker compose -f docker/docker-compose.yml down
```

### Scenario 4: All Services (MongoDB, Redis, Qdrant, Elasticsearch)

```bash
# 1. Start all services
docker compose -f docker/docker-compose.services.yml --profile full --profile ui up -d

# 2. Available services
# MongoDB: localhost:27017
# Redis: localhost:6379
# Qdrant: localhost:6333
# Elasticsearch: localhost:9200
# MongoDB UI: http://localhost:8081
# Redis UI: http://localhost:8082

# 3. Run your app
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python research_cli.py

# 4. Stop
docker compose -f docker/docker-compose.services.yml down
```

## 🧹 Clean Up Commands

```bash
# Stop services only (keep data)
docker compose -f docker/docker-compose.services.yml down

# Stop and remove volumes (fresh start)
docker compose -f docker/docker-compose.services.yml down -v

# Stop everything (full stack)
docker compose -f docker/docker-compose.yml down -v

# Nuclear option - remove everything
docker compose -f docker/docker-compose.services.yml down -v
docker compose -f docker/docker-compose.yml down -v
docker volume prune -f
```

## 📋 Verification Checklist

After starting services, verify:

```bash
# Check containers are running
docker ps
# Should show healthy containers

# Test MongoDB
docker exec research_mongo mongosh --eval "db.version()"
# Should return version

# Test Redis
docker exec research_redis redis-cli ping
# Should return PONG

# Test from host
mongosh mongodb://localhost:27017
redis-cli ping
```

## 🎯 Recommended Test Flow

**For daily development:**
```bash
# Morning
docker compose -f docker/docker-compose.services.yml --profile ui up -d

# Code all day
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
# Edit code, test, repeat...

# Evening
docker compose -f docker/docker-compose.services.yml down
```

**For testing API:**
```bash
# Start services
docker compose -f docker/docker-compose.services.yml up -d

# Terminal 1: Run API
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn src.api.main:app --reload

# Terminal 2: Run tests
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python scripts/test_api.py

# Stop
docker compose -f docker/docker-compose.services.yml down
```

## 🐛 Troubleshooting

**Services won't start:**
```bash
# Check ports
lsof -i :27017
lsof -i :6379

# View logs
docker compose -f docker/docker-compose.services.yml logs
```

**Can't connect:**
```bash
# Check services are healthy
docker ps

# Wait a bit longer
sleep 10

# Check again
docker exec research_mongo mongosh --eval "db.version()"
```

**Need fresh start:**
```bash
# Complete cleanup
docker compose -f docker/docker-compose.services.yml down -v
docker volume prune -f

# Start fresh
docker compose -f docker/docker-compose.services.yml up -d
```

---
**Current Status:** ✅ All containers stopped, volumes removed
**Ready for:** Fresh testing from scratch
**Date:** 2026-02-06
