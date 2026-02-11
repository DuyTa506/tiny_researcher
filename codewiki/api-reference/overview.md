# API Reference Overview

```text
Related code:
- backend/src/api/routes/conversation.py:1-200
- backend/src/api/routes/papers.py:1-150
- backend/src/api/routes/reports.py:1-150
- backend/src/api/main.py:1-80
- README.md:127-161
```

## API Surface Map

**Base URL**: `/api/v1`

**7 Routers**:
1. `/auth` - JWT authentication (login, register, refresh)
2. `/conversations` - Research sessions with SSE streaming
3. `/papers` - Paper CRUD + study cards + evidence
4. `/reports` - Report CRUD + export (Markdown/HTML)
5. `/sources` - Manual source addition (URLs)
6. `/plan` - Research plan generation/editing
7. `/ws` - WebSocket alternative to SSE (deprecated)

## Authentication

**JWT Bearer Token**:
```bash
# Login
POST /api/v1/auth/login
{"email": "user@example.com", "password": "secret"}

# Response
{"access_token": "eyJ...", "refresh_token": "eyJ..."}

# Authenticated Request
curl -H "Authorization: Bearer eyJ..." \
  https://localhost/api/v1/papers
```

**Current Status**: Basic JWT auth implemented but **not enforced** (development mode). No RBAC or permissions yet.

## Key Endpoints

### Conversations (Research Sessions)

```bash
# Create session
POST /api/v1/conversations
{"topic": "transformer architectures"}
→ {"conversation_id": "abc-123", "state": "IDLE"}

# Send message (triggers pipeline)
POST /api/v1/conversations/abc-123/messages
{"content": "transformer architectures"}
→ 202 Accepted (processing async)

# SSE Stream (real-time updates)
GET /api/v1/conversations/abc-123/stream
→ event: progress
   data: {"phase": "planning", "message": "Generating plan..."}
→ event: plan
   data: {"queries": ["transformer attention", ...]}
→ event: papers_collected
   data: {"papers": [{...}]}
→ event: complete
   data: {"pass_rate": 0.93}

# Get conversation state
GET /api/v1/conversations/abc-123
→ {"state": "COMPLETE", "messages": [...], "plan": {...}}

# Delete session
DELETE /api/v1/conversations/abc-123
→ 204 No Content
```

### Papers

```bash
# List papers (pagination + filters)
GET /api/v1/papers?status=EXTRACTED&limit=20&offset=0
→ {"items": [{...}], "total": 150}

# Get paper details
GET /api/v1/papers/{id}
→ {"title": "...", "status": "EXTRACTED", "relevance_score": 9.2}

# Get study card
GET /api/v1/papers/{id}/study-card
→ {"problem": "...", "method": "...", "datasets": [...]}

# Get evidence spans
GET /api/v1/papers/{id}/evidence-spans
→ [{"snippet": "...", "locator": {"page": 3}, "confidence": 0.92}]
```

### Reports

```bash
# List reports
GET /api/v1/reports?search=transformer&limit=10
→ {"items": [{...}], "total": 25}

# Get report
GET /api/v1/reports/{id}
→ {"title": "...", "content": "# Research Report\n...", "language": "en"}

# Export report
GET /api/v1/reports/{id}/export?format=markdown
→ Content-Type: text/markdown
   Content-Disposition: attachment; filename="report.md"

# Get claims
GET /api/v1/reports/{id}/claims
→ [{"claim_text": "...", "evidence_span_ids": ["span-1"]}]

# Get taxonomy
GET /api/v1/reports/{id}/taxonomy
→ {"dimensions": ["themes", "datasets"], "matrix": [[...]]}
```

## Error Responses

```json
{
  "detail": "Paper not found",
  "status_code": 404
}
```

**Common Status Codes**:
- `200 OK` - Success
- `202 Accepted` - Async processing started
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Missing/invalid token
- `404 Not Found` - Resource doesn't exist
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Backend failure

## OpenAPI Documentation

Interactive docs available at `/docs` (Swagger UI) and `/redoc` (ReDoc):
- `http://localhost:8000/docs` (local)
- `http://localhost/api/v1/docs` (docker-compose with nginx)

## Rate Limits

**Current**: None (development)

**Planned**:
- 100 requests/minute per user
- 10 concurrent research sessions per user
- 1000 LLM tokens/minute global limit
