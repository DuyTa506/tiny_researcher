# Tiny Researcher

AI-powered research assistant for paper discovery, evidence extraction, and citation-grounded report synthesis.

## Features

- **Authentication** - JWT-based auth with email verification, password reset, Google OAuth
- **Research Pipeline** - 10-phase citation-first workflow with HITL approval gates
- **Multi-Source Search** - Parallel search across ArXiv, OpenAlex with intelligent deduplication
- **Evidence Extraction** - Schema-driven extraction with page-level locators
- **Citation Grounding** - Every claim backed by verbatim evidence spans with citations
- **CRUD Management** - Full management for papers, reports, and research sessions
- **Real-time Updates** - SSE streaming for live pipeline progress
- **Export** - Download reports as Markdown or HTML

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 16, React 19, TypeScript, React Query, CSS Modules |
| **Backend** | FastAPI, Python 3.11, Pydantic v2 |
| **Database** | MongoDB (Motor async), Redis |
| **LLM** | OpenAI GPT-4, Google Gemini |
| **Vector DB** | Qdrant (embeddings) |
| **Deployment** | Docker Compose, Nginx |

## Quick Start

### Using Docker (Recommended)

```bash
# 1. Clone and navigate
git clone <repo-url>
cd tiny_researcher

# 2. Set up environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys (GEMINI_API_KEY or OPENAI_API_KEY)

# 3. Start all services
docker compose up --build

# 4. Access the application
# Frontend: http://localhost
# Backend API: http://localhost/api/v1/docs
# MongoDB: localhost:27017
# Redis: localhost:6379
```

### Manual Development Setup

#### Backend

```bash
cd backend

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spacy model
python -m spacy download en_core_web_sm

# Set up services
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6379:6379 redis:7

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run backend
uvicorn src.api.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set up environment (optional, uses /api/v1 by default)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

# Run frontend
npm run dev

# Access at http://localhost:3000
```

## Project Structure

```
tiny_researcher/
├── backend/                 # FastAPI backend
│   ├── src/
│   │   ├── api/            # REST API routes
│   │   ├── auth/           # Authentication system
│   │   ├── conversation/   # Dialogue management
│   │   ├── core/           # Config, models, database
│   │   ├── planner/        # Research planning
│   │   ├── research/       # Pipeline implementation
│   │   ├── storage/        # MongoDB repositories
│   │   └── tools/          # Search tools
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/           # App Router pages
│   │   ├── components/    # React components
│   │   ├── hooks/         # React Query hooks
│   │   ├── services/      # API clients
│   │   └── lib/           # Utils, types, constants
│   ├── Dockerfile
│   └── package.json
├── nginx/                  # Reverse proxy config
│   └── nginx.conf
├── docker-compose.yml      # Full stack orchestration
└── README.md              # This file
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with credentials
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user
- `POST /api/v1/auth/google` - Google OAuth

### Papers
- `GET /api/v1/papers` - List papers (pagination, filters)
- `POST /api/v1/papers` - Create paper
- `GET /api/v1/papers/{id}` - Get paper details
- `PUT /api/v1/papers/{id}` - Update paper
- `DELETE /api/v1/papers/{id}` - Delete paper
- `GET /api/v1/papers/{id}/study-card` - Get study card
- `GET /api/v1/papers/{id}/evidence-spans` - Get evidence

### Reports
- `GET /api/v1/reports` - List reports (pagination, search)
- `GET /api/v1/reports/{id}` - Get report
- `PUT /api/v1/reports/{id}` - Update report
- `DELETE /api/v1/reports/{id}` - Delete report
- `GET /api/v1/reports/{id}/export?format=markdown|html` - Export report
- `GET /api/v1/reports/{id}/claims` - Get claims
- `GET /api/v1/reports/{id}/taxonomy` - Get taxonomy matrix

### Conversations
- `GET /api/v1/conversations` - List sessions
- `POST /api/v1/conversations` - Create session
- `POST /api/v1/conversations/{id}/messages` - Send message
- `GET /api/v1/conversations/{id}/stream` - SSE stream
- `DELETE /api/v1/conversations/{id}` - Delete session

Full API docs: http://localhost:8000/docs (when running)

## Environment Variables

### Backend (.env)

```bash
# Database
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=research_assistant
REDIS_URL=redis://localhost:6379/0

# LLM (at least one required)
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Authentication (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Email (optional, logs in dev if not set)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@example.com

# OAuth (optional)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# OpenAlex (optional, for 10x rate limit)
OPENALEX_MAILTO=your_email@example.com

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env.local)

```bash
# API URL (default: /api/v1 for nginx proxy)
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Development

### Backend Development

```bash
cd backend

# Activate virtual environment
source .venv/bin/activate

# Run with hot reload
uvicorn src.api.main:app --reload

# Run tests
pytest

# Code formatting
black src/
ruff check src/
```

### Frontend Development

```bash
cd frontend

# Development server
npm run dev

# Build for production
npm run build

# Run production build
npm run start

# Lint
npm run lint
```

## Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| `nginx` | 80 | Reverse proxy |
| `frontend` | 3000 | Next.js app |
| `backend` | 8000 | FastAPI app |
| `mongo` | 27017 | MongoDB database |
| `redis` | 6379 | Redis cache |

### Docker Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Rebuild specific service
docker compose up -d --build backend

# Stop all services
docker compose down

# Stop and remove volumes (clean state)
docker compose down -v
```

## Research Pipeline Phases

1. **Clarify** - Refine research question through dialogue
2. **Plan** - Generate search queries and strategy
3. **Collect & Dedup** - Multi-source parallel search
4. **Screening** - Filter papers by relevance (3-tier)
5. **Approval Gate** - HITL approval for PDF downloads
6. **PDF Loading** - Fetch full text with page mapping
7. **Evidence Extraction** - Extract structured evidence
8. **Clustering** - Group papers by themes
9. **Taxonomy** - Build multi-dimensional matrix
10. **Claims + Gaps** - Generate grounded claims
11. **Grounded Synthesis** - Write cited report
12. **Citation Audit** - Verify all citations

## Troubleshooting

### Backend won't start

```bash
# Check MongoDB is running
docker ps | grep mongo

# Check Redis is running
docker ps | grep redis

# Check environment variables
cat backend/.env | grep -v "^#" | grep -v "^$"

# Check Python version
python --version  # Should be 3.11+
```

### Frontend build fails

```bash
# Clear Next.js cache
cd frontend
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

### Docker services won't connect

```bash
# Check all services are healthy
docker compose ps

# Check logs
docker compose logs backend
docker compose logs frontend

# Restart services
docker compose restart
```

### MongoDB connection error

```bash
# Ensure MongoDB is accessible
docker exec -it tiny_researcher-mongo-1 mongosh --eval "db.adminCommand('ping')"

# Check backend connection string
docker compose exec backend env | grep MONGO_URL
```

## Production Deployment

### Security Checklist

- [ ] Generate strong `JWT_SECRET_KEY` (32+ chars random)
- [ ] Configure SMTP for email verification
- [ ] Set up SSL/TLS certificate (use Let's Encrypt)
- [ ] Enable CORS whitelist (remove `allow_origins=["*"]`)
- [ ] Set secure MongoDB credentials
- [ ] Configure Redis password
- [ ] Review and restrict API rate limits
- [ ] Enable logging and monitoring

### Nginx SSL Configuration

Update `nginx/nginx.conf`:

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... rest of config
}
```

### Environment for Production

```bash
# Backend
ENVIRONMENT=production
LOG_LEVEL=WARNING
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Frontend
NODE_ENV=production
```

## Acknowledgments

This project was inspired by and references:

- **[LobeHub](https://github.com/lobehub/lobehub)** - Project structure and organization principles
- **[UI/UX Pro Max Skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)** - UI/UX first design methodology

## License

[Your License Here]

## Contributing

[Contributing Guidelines Here]

## Support

For issues and questions, please open a GitHub issue.
