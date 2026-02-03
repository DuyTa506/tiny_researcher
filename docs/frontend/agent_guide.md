# Frontend Agent Guide

> **Tài liệu dành cho Frontend AI Agent** để phát triển ứng dụng Research Assistant.

## Project Structure (Next.js App Router)

```
research_assistant_fe/
├── src/
│   ├── app/                       # App Router Pages
│   │   ├── layout.tsx             # Root layout (Fonts, Providers)
│   │   ├── page.tsx               # Dashboard (Home)
│   │   ├── sources/
│   │   │   ├── page.tsx           # Source Manager List
│   │   │   └── loading.tsx
│   │   ├── papers/
│   │   │   ├── page.tsx           # Paper Workspace
│   │   │   └── [id]/              # Paper Detail
│   │   │       └── page.tsx
│   │   └── reports/
│   │       └── page.tsx           # Report Viewer
│   │
│   ├── components/                # UI Components
│   │   ├── ui/                    # Base Components (Atomic)
│   │   │   ├── Button/
│   │   │   │   ├── index.tsx
│   │   │   │   └── styles.module.css
│   │   │   ├── Card/
│   │   │   └── Input/
│   │   ├── modules/               # Domain Components
│   │   │   ├── PaperList/
│   │   │   ├── SourceForm/
│   │   │   └── ReportViewer/
│   │   └── layout/                # Layout Components
│   │       ├── Sidebar/
│   │       └── Header/
│   │
│   ├── hooks/                     # Custom React Hooks
│   │   ├── usePapers.ts
│   │   └── useSources.ts
│   │
│   ├── services/                  # API Clients
│   │   ├── api.ts                 # Axios instance
│   │   ├── papers.ts
│   │   └── reports.ts
│   │
│   ├── lib/                       # Utilities
│   │   ├── utils.ts
│   │   ├── constants.ts
│   │   └── types.ts               # TypeScript Interfaces
│   │
│   └── styles/                    # Global Styles
│       ├── globals.css            # CSS Variables & Reset
│       └── mixins.css
│
├── public/                        # Static Assets
├── Dockerfile
├── next.config.js
└── package.json
```

## Tech Stack & Standards

### Core Setup
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Package Manager**: npm / pnpm

### Styling Rules
1.  **NO TailwindCSS**: Sử dụng Vanilla CSS + CSS Modules.
2.  **Naming Convention**: `styles.module.css` đặt cùng folder với component.
3.  **CSS Variables**: Định nghĩa màu sắc, spacing trong `globals.css` và dùng lại.
    ```css
    :root {
      --primary: #2563eb;
      --surface: #ffffff;
      --text-main: #1e293b;
    }
    ```

### State Management
- **Server State**: Sử dụng **TanStack Query (React Query)** cho tất cả API calls.
- **Client State**: Sử dụng `useState` cho local UI state. Hạn chế Redux/Zustand trừ khi quá phức tạp.

### API Integration
- Sử dụng **Repository Pattern** trong `src/services`.
- Không gọi `fetch` trực tiếp trong Component.

## Coding Checklist

### 1. Setup Phase
- [ ] Initialize Next.js project (TypeScript, ESLint).
- [ ] Setup `globals.css` with CSS Variables (Theming).
- [ ] Setup Axios instance with Interceptors (Base URL).
- [ ] Configure Docker environment.

### 2. Component Implementation
- [ ] Create Base Components: `Button`, `Input`, `Card`, `Modal`, `Badge`.
- [ ] Create Layout Components: `Sidebar` (Navigation), `Header` (Search).
- [ ] Implement `SourceForm` (Validation).
- [ ] Implement `PaperCard` (Hover effects, Summary snippet).

### 3. Feature Implementation
- [ ] **Dashboard**: Stats Overview using Recharts.
- [ ] **Source Manager**: Table view, Add/Edit/Delete actions.
- [ ] **Paper Workspace**: Infinite Scroll List, Filter Sidebar.
- [ ] **Report Viewer**: Markdown Rendering styling.

### 4. Optimization
- [ ] Implement Loading Skeletons for all data fetching states.
- [ ] Optimize Fonts (next/font).
- [ ] Dockerize for deployment.
