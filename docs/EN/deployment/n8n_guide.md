# n8n Deployment & Integration Guide

## Overview
In this Microservices architecture, **n8n** acts as the **Orchestrator** and **Event Trigger**. Instead of implementing complex processing logic (Cluster, Summarize) within n8n nodes (which is hard to debug/version control), n8n will call the **Backend API (Python Services)** to execute heavy tasks.

## Deployment Architecture

Use Docker Compose to deploy n8n alongside the current stack.

### `docker-compose.yml` (Configuration)

```yaml
version: '3.8'

services:
  # ... (Postgres, Redis, API services defined previously)

  n8n:
    image: n8nio/n8n:latest
    container_name: research_n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASS}
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=postgres
      - DB_POSTGRESDB_PORT=5432
      - DB_POSTGRESDB_DATABASE=n8n_flow_db
      - DB_POSTGRESDB_USER=${DB_USER}
      - DB_POSTGRESDB_PASSWORD=${DB_PASS}
      # Configure Webhook URL for external/browser access
      - WEBHOOK_URL=http://localhost:5678/
      # N8N_HOST is for internal binding, WEBHOOK_URL is critical for correct UI links
      - N8N_HOST=n8n
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - research_network
    depends_on:
      - postgres

networks:
  research_network:
    driver: bridge
```

> **Note**: It is recommended to create a separate database (e.g., `n8n_flow_db`) for n8n system data, keeping it isolated from `research_db` which stores our research papers.

## Integration Patterns

How n8n integrates with the Python Backend:

### Pattern 1: Scheduled Ingestion Trigger
**Scenario**: "Every morning at 8am, tell Backend to crawl new data."
- **n8n Workflow**:
  1. **Cron Node**: `0 8 * * *`.
  2. **HTTP Request Node**:
     - Method: `POST`
     - URL: `http://api-service:8000/api/v1/ingestion/trigger-all`
     - Auth: API Key Header.

### Pattern 2: Delivery & Notification Hook
**Scenario**: "When Backend finishes a report, send via Telegram."
- **Logic**: Backend (Python) sends a Webhook to n8n after report creation.
- **n8n Workflow**:
  1. **Webhook Node**: `POST /webhook/report-ready`
  2. **Telegram Node**: Send message "Report [ID] is ready!".
  3. **Gmail Node**: Send email with Markdown attachment.

### Pattern 3: Human-in-the-loop (Optional)
**Scenario**: Approve report before publishing.
- **n8n Workflow**:
  1. Webhook receives Draft Report.
  2. **Slack Node**: Send message with "Approve" / "Reject" Buttons.
  3. **Wait for Trigger Node**: Wait for user action.
  4. If Approve -> Call Backend `PUT /api/v1/reports/{id}/publish`.

## Recommended Workflows

### 1. `Main_Orchestrator.json`
Main workflow to manage system-wide schedule.
- **Nodes**:
  - `Schedule Trigger` (Daily).
  - `HTTP Request` -> Call `ingestion-service`.
  - `Wait` (e.g., 30 mins) -> Wait for ingestion completion.
  - `HTTP Request` -> Call `reporting-service` (Generate Report).

### 2. `Alert_System.json`
Workflow to receive error events or notifications from Backend.
- **Nodes**:
  - `Webhook` (Method: POST).
  - `Switch`: Check `alert_type` (Error, Info, Warning).
  - `Slack/Telegram`: Route message to appropriate channel.

## Environment Configuration

Configure environment variables in `.env` for n8n and Backend to "understand" each other:

```ini
# .env shared configuration

# Internal Network URLs
BACKEND_API_URL=http://api-service:8000
N8N_WEBHOOK_URL=http://n8n:5678/webhook

# Shared Secrets
WEBHOOK_SECRET=secure_random_string_here_123
```
