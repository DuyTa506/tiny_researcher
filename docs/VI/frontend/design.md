# Frontend Design - Research Assistant Framework

## Overview
Frontend là giao diện tương tác chính cho Researcher, được xây dựng theo kiến trúc **Single Page Application (SPA)** hiện đại, tách biệt hoàn toàn với Backend API. Thiết kế tập trung vào trải nghiệm đọc (Readability) và khả năng quản lý thông tin khoa học hiệu quả.

## Tech Stack
- **Framework**: Next.js 14+ (App Router)
- **State Management**: React Query (TanStack Query) - *Tối ưu cho server state sync*.
- **Styling**: **Vanilla CSS (CSS Modules)**.
  - Tuân thủ quy tắc: Không dùng TailwindCSS.
  - Sử dụng CSS Variables cho Theming (Dark/Light mode).
  - Modular hóa style theo từng Component (`*.module.css`).
- **Icons**: Lucide React.
- **Charts**: Recharts (biểu đồ thống kê).

## Architecture Diagram

```mermaid
graph TD
    User[👤 Researcher] -->|HTTPS| CDN[CDN / Edge]
    CDN -->|Serve Static| FE[Next.js Client]
    
    subgraph Frontend Logic
        Page[Pages / Views] --> Components[UI Components]
        Components --> Hooks[Custom Hooks]
        Hooks --> Services[API Services]
        Services -->|Axios/Fetch| Backend[Backend API]
    end
    
    style FE fill:#FFD966
    style Backend fill:#DAE8FC
```

## UI/UX Modules

### 1. Dashboard (Home)
- **Overview Stats**: Số lượng bài báo mới tuần này, số bài đã đọc, các topic đang hot.
- **Micro-interactions**: Hover vào card bài báo thấy tóm tắt nhanh.
- **Aesthetics**: Glassmorphism cho các card, gradient background tinh tế.

### 2. Source Manager (`/sources`)
- **Giao diện**: Table/Grid view quản lý các nguồn tin.
- **Actions**: 
  - Add Source (Link/Keyword input form).
  - Toggle Active/Inactive.
  - Edit Schedule.
- **Validation**: Real-time validation khi nhập URL RSS.

### 3. Researcher Workspace (`/papers`)
- **Layout**: 2-Column (List bên trái, Detail bên phải) hoặc Masonry Grid.
- **Features**:
  - Filter bar (Date, Relevance Score, Topic).
  - Search bar (Full-text search).
  - "Save to Collection" button.

### 4. Report Viewer (`/reports`)
- **Giao diện**: Document Reader (giống Notion/Medium).
- **Typography**: Sử dụng font chữ serif hiện đại cho nội dung báo cáo (e.g., *Merriweather* hoặc *Lora*) để tối ưu trải nghiệm đọc sâu.
- **Export**: Nút Download Markdown/PDF.

## Component Design (Modular CSS)

Cấu trúc thư mục theo hướng Modular:
```
src/
  components/
    Button/
      index.tsx
      styles.module.css  <-- Vanilla CSS scope local
    Card/
      index.tsx
      styles.module.css
  app/
    dashboard/
      page.tsx
      page.module.css
```

**Ví dụ `styles.module.css`**:
```css
/* Sử dụng CSS Variables định nghĩa từ global */
.card {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.5rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
```

## API Integration

Sử dụng **Repository Pattern** ở frontend để decouple API call:

```typescript
// services/papers.ts
export const getPapers = async (filters: PaperFilter): Promise<Paper[]> => {
  const params = new URLSearchParams(filters);
  const res = await fetch(`/api/v1/papers?${params}`);
  return res.json();
};

// hooks/usePapers.ts
export const usePapers = (filters: PaperFilter) => {
  return useQuery({
    queryKey: ['papers', filters],
    queryFn: () => getPapers(filters)
  });
};
```

## Deployment Frontend
 Frontend sẽ được đóng gói thành Docker Image riêng biệt, giao tiếp với Backend qua Internal Network hoặc Public API Gateway.

```dockerfile
# Dockerfile UI
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
CMD ["npm", "start"]
```
