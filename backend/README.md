# Backend Development Guide

Complete backend guide for the Tiny Researcher AI research assistant.

## Architecture Overview

The backend is a **FastAPI** application implementing a 10-phase citation-first research pipeline with authentication, real-time streaming, and MongoDB persistence.

### Tech Stack

- **Framework**: FastAPI 0.109+, Uvicorn ASGI server
- **Language**: Python 3.11+
- **Database**: MongoDB (Motor async driver)
- **Cache**: Redis
- **LLM**: OpenAI GPT-4, Google Gemini
- **Vector DB**: Qdrant
- **Auth**: JWT (PyJWT), bcrypt, OAuth 2.0

### Project Structure

```
backend/
├── src/
│   ├── api/                    # REST API layer
│   │   ├── main.py            # FastAPI app + routes
│   │   └── routes/            # Endpoint modules
│   │       ├── auth.py        # Authentication (11 endpoints)
│   │       ├── papers.py      # Papers CRUD (8 endpoints)
│   │       ├── reports.py     # Reports CRUD (7 endpoints)
│   │       ├── conversation.py # Sessions (5 endpoints)
│   │       ├── planner.py     # Planning
│   │       ├── sources.py     # Source processing
│   │       └── websocket.py   # WebSocket streaming
│   ├── auth/                   # Authentication system
│   ├── conversation/           # Dialogue management
│   ├── core/                   # Core infrastructure
│   ├── planner/                # Research planning
│   ├── research/               # Research workflow
│   ├── storage/                # Data persistence
│   ├── tools/                  # Tool system
│   └── utils/                  # Utilities
├── Dockerfile
└── requirements.txt
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up services
docker run -d -p 27017:27017 mongo:7
docker run -d -p 6379:6379 redis:7

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run server
uvicorn src.api.main:app --reload
```

API docs: http://localhost:8000/docs

For full documentation, see the main README.md in the project root.
