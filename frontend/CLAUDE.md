# CLAUDE.md (Frontend)

This file provides guidance to Claude Code (claude.ai/code) when working with code in the **Tiny Researcher frontend** (`frontend/`).

## Project Overview

**Tiny Researcher Frontend** is a Next.js application that provides the interactive research workspace UI for the Tiny Researcher system.  
It connects to the Python FastAPI backend to drive the research pipeline (clarify → plan → collect → screen → extract → synthesize → audit).

**Current Status:** Modern App Router Next.js app with React Query, Axios-based API layer, and dedicated research views for conversations, papers, and reports.

## Tech Stack

| Category | Technology |
|----------|------------|
| **Framework** | Next.js 16.1.x (App Router) |
| **Language** | TypeScript |
| **UI Library** | React 19.x |
| **State Management** | @tanstack/react-query (server state) |
| **Styling** | CSS Modules |
| **Icons** | lucide-react |
| **HTTP Client** | Axios |
| **Markdown Rendering** | react-markdown, remark-gfm |
| **Charts** | Recharts |
| **Linting** | ESLint |

## Project Structure

The frontend is a standard App Router Next.js app with a small service + hooks layer for API access.

```text
frontend/
├── .agents/                 # Agent workflows / skills for this project
├── public/                  # Static assets
└── src/
    ├── app/                 # Next.js App Router entry points
    │   ├── layout.tsx       # Root layout + providers
    │   ├── page.tsx         # Dashboard / entry screen
    │   ├── papers/          # Paper list & detail routes
    │   ├── reports/         # Report listing & viewing
    │   └── research/        # Active research session views
    ├── components/
    │   ├── chat/            # Chat interface (messages, input, stream)
    │   ├── layout/          # Header, sidebar, shell components
    │   └── ui/              # Reusable UI primitives (buttons, cards, etc.)
    ├── hooks/               # React Query hooks, streaming hooks
    ├── lib/                 # Utilities (constants, helpers)
    ├── services/            # Axios instances and API clients
    └── styles/              # CSS modules and global styles
```

### Architecture Map

| Layer | Location | Description |
|-------|----------|-------------|
| **UI Components** | `src/components/{ui,chat,layout}` | Presentational and feature components. |
| **Routing / Pages** | `src/app` | App Router routes for dashboard, research, papers, reports. |
| **Global Providers** | `src/app/layout.tsx`, `src/app/providers.tsx` | React Query client, theme, global context. |
| **Data Fetching** | `src/services`, `src/hooks` | Axios-based API clients + React Query hooks. |
| **Config / Utils** | `src/lib` | Constants (e.g. API base URL), helpers. |
| **Styles** | `src/styles` | App-wide styles and CSS modules. |

## Backend Integration

- The frontend talks to the backend FastAPI service via a base URL configured with `NEXT_PUBLIC_API_URL`.  
- Default development target (can be overridden in `.env.local`):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**Key expectations for agents:**

1. Prefer going through the existing Axios instance (in `src/services`) instead of creating ad-hoc `fetch` calls.
2. Expose new backend endpoints through a small service function (`src/services/*.ts`), then wrap it in a React Query hook in `src/hooks`.
3. Keep components mostly presentational; move side effects and data fetching into hooks.

## Development Commands

The frontend uses a standard Node.js toolchain. Use your preferred package manager (`pnpm`, `npm`, or `yarn`); adapt commands as needed.

```bash
# Install dependencies (example with pnpm)
pnpm install

# or with npm
npm install

# Run dev server
pnpm dev          # or: npm run dev

# Build for production
pnpm build        # or: npm run build

# Start production build
pnpm start        # or: npm run start

# Lint
pnpm lint         # or: npm run lint
```

## Entry Points (Frontend)

### Starting the app (development)

1. Ensure the backend API is running and reachable at `NEXT_PUBLIC_API_URL`.  
2. From `frontend/`, run:

```bash
pnpm dev   # or: npm run dev
```

3. Open `http://localhost:3000` in the browser.

### Research Flow in the UI

Typical usage pattern in the app:

1. User opens the dashboard or research page (`/research`).  
2. User enters a research topic and optional configuration (language, limits).  
3. Frontend creates or resumes a conversation / research session via the backend API.  
4. React Query hooks subscribe to research progress (polling or SSE / WebSocket if implemented).  
5. UI updates chat messages, phase progress, and final reports as data comes back from the backend.

Agents should **reuse existing hooks and services** when extending this flow (e.g., new views on evidence, taxonomy, or audit results).

## Development Strategy (Frontend)

### Code Organization Principles

1. **Component-first UI** – Keep UI components small, focused, and reusable.
2. **Hooks for logic** – Place data fetching and non-trivial state logic into hooks in `src/hooks`.
3. **Single source of API truth** – Centralize all HTTP calls in `src/services` through a shared Axios instance.
4. **Type-safe** – Use TypeScript types/interfaces for API responses and component props.
5. **Progressive enhancement** – Start from a simple version and layer in more interactivity or sophistication only when needed.

### Common Patterns

**React Query data fetching:**

```ts
// Pseudocode / pattern – check existing hooks for exact details
import { useQuery, useMutation } from "@tanstack/react-query";
import { getSomething, createSomething } from "@/services/api";

export function useSomething(id: string) {
  return useQuery({
    queryKey: ["something", id],
    queryFn: () => getSomething(id),
  });
}
```

**Separation of concerns:**

- Components under `src/components/ui` should have **no direct API calls**.  
- `src/components/chat` / `src/app/research` may use hooks that wrap API calls, but should not contain raw Axios logic.

### Styling Guidelines

- Prefer **CSS Modules** for component-scoped styles.  
- Keep global CSS to layout / theming only.  
- When adding new UI components, mirror the structure and naming from existing `ui` components.

## Current Limitations & Notes

1. The frontend assumes the backend API contract described in `backend/docs` and `backend/CLAUDE.md`. If you change backend routes or payloads, update `src/services` and related types here.
2. Authentication is not yet implemented; avoid adding auth flows unless the backend is ready.
3. Streaming (SSE / WebSocket) integration may be partial; reuse / extend any existing streaming hooks instead of reimplementing from scratch.

## Quick Reference

| Task | Command (example with pnpm) |
|------|-----------------------------|
| Install deps | `pnpm install` |
| Run dev server | `pnpm dev` |
| Build | `pnpm build` |
| Start production | `pnpm start` |
| Lint | `pnpm lint` |

## Documentation

- `frontend/project_overview.md` – High-level overview of the frontend app.  
- `backend/CLAUDE.md` – Backend-specific guidance (API, pipeline, storage).  
- Root `CLAUDE.md` – Monorepo-level guidance and entry points.

# Tiny Researcher Project Overview

## Project Description

**Tiny Researcher** is an AI-powered research assistant designed for paper discovery, evidence extraction, and citation-grounded report synthesis. It features a pipeline that guides users through clarifying research questions, planning, collecting papers, and generating synthesized reports.

## Tech Stack

| Category | Technology |
|----------|------------|
| **Framework** | Next.js 16.1.6 + React 19.2.3 |
| **Language** | TypeScript |
| **Routing** | Next.js App Router |
| **State Management** | @tanstack/react-query (Server State) |
| **Styling** | CSS Modules |
| **Icons** | lucide-react |
| **Data Fetching** | Axios |
| **Data Visualization** | Recharts |
| **Markdown Rendering** | react-markdown, remark-gfm |
| **Linting** | ESLint |

## Project Structure

The project is structured as a standard Next.js App Router application.

```mermaid
graph TD
    Root[frontend/] --> Agents[.agents/]
    Root --> Public[public/]
    Root --> Src[src/]
    Src --> App[app/]
    Src --> Components[components/]
    Src --> Hooks[hooks/]
    Src --> Lib[lib/]
    Src --> Services[services/]
    Src --> Styles[styles/]
    App --> RootPage[page.tsx (Dashboard)]
    App --> Papers[papers/]
    App --> Reports[reports/]
    App --> Research[research/]
    Components --> Chat[chat/]
    Components --> Layout[layout/]
    Components --> UI[ui/]
```

## Architecture Map

| Layer | Location | Description |
|-------|----------|-------------|
| **UI Components** | `src/components/{ui,chat,layout}` | Reusable presentation components. |
| **Pages/Routes** | `src/app` | Application routes and page-specific logic. |
| **Layouts** | `src/app/layout.tsx`, `src/components/layout` | Global application shell and providers. |
| **Data Fetching** | `src/services`, `src/hooks` | Service functions wrapping Axios calls; React Query hooks. |
| **State** | `src/app/providers.tsx` | Global providers (React Query Client). |
| **Config/Utils** | `src/lib` | Constants (`constants.ts`) and utility functions (`utils.ts`). |
| **Backend API** | External (FastAPI) | Connected via `API_BASE_URL` (default: `http://localhost:8000/api/v1`). |

## Data Flow

User actions trigger React components, which use custom hooks (often wrapping React Query) to call service functions. These services use a configured Axios instance to communicate with the Python FastAPI backend.

## Key Features & Pipelines

The application is built around a research pipeline with the following phases:

1.  **Clarify**: Refine the research question.
2.  **Plan**: Create a research plan.
3.  **Collect & Dedup**: Search for and deduplicate papers.
4.  **Screening**: Filter papers based on relevance.
5.  **Approval Gate**: Human-in-the-loop approval.
6.  **PDF Loading**: Fetch full text of papers.
7.  **Evidence Extraction**: Extract key findings.
8.  **Clustering**: Group similar findings.
9.  **Taxonomy**: Organize findings into a structure.
10. **Claims + Gaps**: Identify supported claims and missing info.
11. **Grounded Synthesis**: Write the report.
12. **Citation Audit**: Verify citations.

## Configuration

*   **API URL**: Configurable via `NEXT_PUBLIC_API_URL` env var. Defaults to `http://localhost:8000/api/v1`.
