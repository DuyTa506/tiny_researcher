# n8n Deployment & Integration Guide

## Overview
Trong kiến trúc Microservices này, **n8n** đóng vai trò là **Orchestrator** (người điều phối) và **Event Trigger**. Thay vì viết toàn bộ logic xử lý phức tạp (Cluster, Summarize) bằng n8n nodes (khó debug/git versioning), n8n sẽ gọi sang **Backend API (Python Services)** để thực thi các tác vụ nặng.

## Deployment Architecture

Sử dụng Docker Compose để deploy n8n cùng với stack hiện tại.

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
      # Cấu hình Webhook URL truy cập từ browser/bên ngoài
      - WEBHOOK_URL=http://localhost:5678/
      # N8N_HOST chỉ dùng cho internal binding, nhưng WEBHOOK_URL quan trọng hơn để UI hiện đúng link
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

> **Lưu ý**: Nên tạo một database riêng (VD: `n8n_flow_db`) cho n8n system data, tách biệt với `research_db` chứa dữ liệu bài báo của chúng ta.

## Integration Patterns

Cách n8n tích hợp với Python Backend:

### Pattern 1: Scheduled Ingestion Trigger
**Scenario**: "Mỗi sáng 8h, bảo Backend đi crawl dữ liệu mới."
- **n8n Workflow**:
  1. **Cron Node**: `0 8 * * *`.
  2. **HTTP Request Node**:
     - Method: `POST`
     - URL: `http://api-service:8000/api/v1/ingestion/trigger-all`
     - Auth: API Key Header.

### Pattern 2: Delivery & Notification Hook
**Scenario**: "Khi Backend viết báo cáo xong, hãy gửi Telegram."
- **Logic**: Backend (Python) sau khi tạo report xong sẽ bắn Webhook sang n8n.
- **n8n Workflow**:
  1. **Webhook Node**: `POST /webhook/report-ready`
  2. **Telegram Node**: Send message "Report [ID] đã sẵn sàng!".
  3. **Gmail Node**: Gửi email đính kèm Markdown.

### Pattern 3: Human-in-the-loop (Optional)
**Scenario**: Duyệt báo cáo trước khi publish.
- **n8n Workflow**:
  1. Webhook nhận Report draft.
  2. **Slack Node**: Gửi message có Button "Approve" / "Reject".
  3. **Wait for Trigger Node**: Chờ user bấm nút.
  4. Nếu Approve -> Gọi lại Backend `PUT /api/v1/reports/{id}/publish`.

## Recommended Workflows

### 1. `Main_Orchestrator.json`
Workflow chính để quản lý lịch chạy toàn hệ thống.
- **Nodes**:
  - `Schedule Trigger` (Daily).
  - `HTTP Request` -> Call `ingestion-service`.
  - `Wait` (e.g., 30 mins) -> Đợi ingestion xong.
  - `HTTP Request` -> Call `reporting-service` (Generate Report).

### 2. `Alert_System.json`
Workflow nhận các sự kiện lỗi hoặc thông báo từ Backend.
- **Nodes**:
  - `Webhook` (Method: POST).
  - `Switch`: Kiểm tra `alert_type` (Error, Info, Warning).
  - `Slack/Telegram`: Route tin nhắn tới kênh phù hợp.

## Environment Configuration

Cấu hình environment variables trong `.env` để n8n và Backend "hiểu nhau":

```ini
# .env shared configuration

# Internal Network URLs
BACKEND_API_URL=http://api-service:8000
N8N_WEBHOOK_URL=http://n8n:5678/webhook

# Shared Secrets
WEBHOOK_SECRET=secure_random_string_here_123
```
