# Deployment Guide

Complete guide for deploying Tiny Researcher to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Deployment](#docker-deployment)
3. [Production Configuration](#production-configuration)
4. [Security Checklist](#security-checklist)
5. [SSL/TLS Setup](#ssltls-setup)
6. [Monitoring](#monitoring)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- Server with **4GB+ RAM** (8GB recommended)
- **Docker** 20.10+ and **Docker Compose** 2.0+
- Domain name (optional, for SSL)
- SMTP credentials (for email verification)
- LLM API keys (OpenAI or Google Gemini)

## Docker Deployment

### 1. Clone Repository

```bash
git clone <repository-url>
cd tiny_researcher
```

### 2. Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit configuration
nano backend/.env
```

Required variables:

```bash
# Database
MONGO_URL=mongodb://mongo:27017
MONGO_DB_NAME=research_assistant
REDIS_URL=redis://redis:6379/0

# LLM (at least one required)
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key

# Authentication - CRITICAL: Generate secure secret
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30  # 30 min for production

# Email (required for production)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_USE_TLS=true

# Frontend URL
FRONTEND_URL=https://yourdomain.com

# Production settings
ENVIRONMENT=production
LOG_LEVEL=WARNING
```

### 3. Start Services

```bash
# Build and start all services
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
```

Services will be available at:
- **Frontend**: http://localhost (port 80)
- **Backend API**: http://localhost/api/v1
- **API Docs**: http://localhost/api/v1/docs

### 4. Verify Deployment

```bash
# Check backend health
curl http://localhost/health

# Check frontend
curl -I http://localhost

# Check MongoDB
docker compose exec mongo mongosh --eval "db.adminCommand('ping')"

# Check Redis
docker compose exec redis redis-cli ping
```

## Production Configuration

### Nginx Configuration

Update `nginx/nginx.conf` for production:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 50M;

    # Backend API
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Docker Compose Production Override

Create `docker-compose.prod.yml`:

```yaml
services:
  mongo:
    restart: always
    volumes:
      - /var/lib/mongodb:/data/db  # Persistent storage
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}

  redis:
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - /var/lib/redis:/data

  backend:
    restart: always
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=WARNING

  frontend:
    restart: always
    environment:
      - NODE_ENV=production

  nginx:
    restart: always
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/nginx/ssl:ro  # SSL certificates
```

Deploy with production overrides:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Security Checklist

### Pre-Deployment

- [ ] **JWT Secret**: Generate strong 32+ character random secret
- [ ] **Database Passwords**: Set secure MongoDB and Redis passwords
- [ ] **SMTP Credentials**: Configure email service
- [ ] **SSL Certificate**: Obtain valid SSL certificate
- [ ] **CORS**: Update allowed origins in `backend/src/api/main.py`
- [ ] **Environment**: Set `ENVIRONMENT=production`
- [ ] **Session Expiry**: Reduce JWT expiry to 15-30 minutes
- [ ] **Rate Limiting**: Enable rate limiting (future enhancement)

### Backend Security

Edit `backend/src/api/main.py`:

```python
# CORS - Restrict to your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # NOT "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### Database Security

```bash
# Create MongoDB admin user
docker compose exec mongo mongosh

use admin
db.createUser({
  user: "admin",
  pwd: "secure_password",
  roles: ["root"]
})

# Create application user
use research_assistant
db.createUser({
  user: "app_user",
  pwd: "app_password",
  roles: [{ role: "readWrite", db: "research_assistant" }]
})
```

Update `backend/.env`:

```bash
MONGO_URL=mongodb://app_user:app_password@mongo:27017/research_assistant?authSource=research_assistant
```

## SSL/TLS Setup

### Using Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot

# Stop nginx temporarily
docker compose stop nginx

# Obtain certificate
sudo certbot certonly --standalone -d yourdomain.com

# Certificates will be at /etc/letsencrypt/live/yourdomain.com/

# Mount in docker-compose
# (See production override above)

# Restart nginx
docker compose up -d nginx
```

### Certificate Renewal

```bash
# Dry run
sudo certbot renew --dry-run

# Setup auto-renewal cron job
sudo crontab -e

# Add line (renew at 2am daily)
0 2 * * * certbot renew --quiet && docker compose restart nginx
```

## Monitoring

### Health Checks

```bash
# Backend health
curl https://yourdomain.com/health

# MongoDB
docker compose exec mongo mongosh --eval "db.stats()"

# Redis
docker compose exec redis redis-cli --pass ${REDIS_PASSWORD} INFO server
```

### Logs

```bash
# All logs
docker compose logs -f

# Specific service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend

# Save logs to file
docker compose logs > app.log
```

### Resource Usage

```bash
# Container stats
docker compose stats

# Disk usage
docker system df

# Detailed service info
docker compose ps
docker inspect <container_id>
```

### Monitoring Tools (Optional)

- **Prometheus** + **Grafana** for metrics
- **ELK Stack** for log aggregation
- **Datadog** or **New Relic** for APM

## Backup & Recovery

### MongoDB Backup

```bash
# Create backup directory
mkdir -p /backups/mongodb

# Backup database
docker compose exec mongo mongosh --eval "
  db.adminCommand({
    export: {
      uri: 'mongodb://localhost/research_assistant',
      path: '/data/backup'
    }
  })
"

# Or use mongodump
docker compose exec mongo mongodump \
  --db=research_assistant \
  --out=/data/backup/$(date +%Y%m%d)

# Copy to host
docker cp tiny_researcher-mongo-1:/data/backup /backups/mongodb/
```

### MongoDB Restore

```bash
# Restore from backup
docker compose exec mongo mongorestore \
  --db=research_assistant \
  /data/backup/20240101/research_assistant
```

### Automated Backups

Create backup script `/usr/local/bin/backup-mongo.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
docker compose -f /path/to/docker-compose.yml exec -T mongo \
  mongodump --db=research_assistant --gzip --archive > \
  ${BACKUP_DIR}/research_assistant_${DATE}.gz

# Keep only last 7 days
find ${BACKUP_DIR} -name "*.gz" -mtime +7 -delete
```

Schedule with cron:

```bash
sudo crontab -e

# Add line (backup daily at 3am)
0 3 * * * /usr/local/bin/backup-mongo.sh
```

### Redis Persistence

Redis is configured for RDB snapshots. Data persists in volume.

```bash
# Force save
docker compose exec redis redis-cli --pass ${REDIS_PASSWORD} SAVE

# Backup RDB file
docker cp tiny_researcher-redis-1:/data/dump.rdb /backups/redis/
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Check memory
free -h

# Restart all services
docker compose restart

# Clean rebuild
docker compose down
docker compose up -d --build --force-recreate
```

### Database Connection Errors

```bash
# Check MongoDB is running
docker compose ps mongo

# Test connection
docker compose exec mongo mongosh --eval "db.adminCommand('ping')"

# Check network
docker network inspect tiny_researcher_default

# Verify credentials
cat backend/.env | grep MONGO_URL
```

### Frontend 502 Error

```bash
# Check frontend is running
docker compose ps frontend

# Check frontend logs
docker compose logs frontend

# Check nginx config
docker compose exec nginx nginx -t

# Reload nginx
docker compose exec nginx nginx -s reload
```

### High Memory Usage

```bash
# Check container stats
docker compose stats

# Limit resources in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

### Performance Issues

```bash
# Enable MongoDB indexes
docker compose exec mongo mongosh

use research_assistant
db.papers.createIndex({ plan_id: 1, relevance_score: -1 })
db.reports.createIndex({ created_at: -1 })
db.users.createIndex({ email: 1 }, { unique: true })

# Clear Redis cache
docker compose exec redis redis-cli --pass ${REDIS_PASSWORD} FLUSHDB
```

## Scaling

### Horizontal Scaling

Deploy multiple backend instances behind nginx:

```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}
```

### Database Scaling

- **MongoDB Replica Set**: For high availability
- **Redis Cluster**: For distributed caching
- **Read Replicas**: For read-heavy workloads

### CDN

Use CDN for static assets:

- **Cloudflare**
- **AWS CloudFront**
- **Fastly**

## Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild containers
docker compose up -d --build

# Run migrations (if any)
docker compose exec backend python scripts/migrate.py
```

### Clean Up

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune

# Full cleanup
docker system prune -a --volumes
```

## Support

For production issues:
1. Check logs first: `docker compose logs`
2. Verify configuration: `cat backend/.env`
3. Test health endpoints
4. Review this guide
5. Open GitHub issue with details

## Checklist Summary

**Pre-Deployment**:
- [ ] Generate strong JWT secret
- [ ] Configure SMTP
- [ ] Obtain SSL certificate
- [ ] Set production environment variables
- [ ] Update CORS settings

**Deployment**:
- [ ] Start services with production config
- [ ] Verify all health checks pass
- [ ] Test authentication flow
- [ ] Test API endpoints
- [ ] Verify email delivery

**Post-Deployment**:
- [ ] Setup automated backups
- [ ] Configure monitoring
- [ ] Setup log rotation
- [ ] Test backup/restore procedure
- [ ] Document runbook

**Ongoing**:
- [ ] Monitor resource usage
- [ ] Review logs weekly
- [ ] Update dependencies monthly
- [ ] Test backups monthly
- [ ] Renew SSL certificates
