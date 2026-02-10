# CLAUDE.md (Frontend)

This file provides guidance to Claude Code (claude.ai/code) when working with code in the **Tiny Researcher frontend** (`frontend/`).

## Project Overview

**Tiny Researcher Frontend** is a Next.js application that provides the interactive research workspace UI for the Tiny Researcher system.
It connects to the Python FastAPI backend to drive the research pipeline (clarify → plan → collect → screen → extract → synthesize → audit).

**Current Status:** Modern App Router Next.js app with React Query, Axios-based API layer, SSE streaming, i18n (EN/VI), and dedicated research views for conversations, papers, and reports.

## Tech Stack

| Category | Technology |
|----------|------------|
| **Framework** | Next.js 16.1.x (App Router) |
| **Language** | TypeScript |
| **UI Library** | React 19.x |
| **State Management** | @tanstack/react-query (server state) |
| **Styling** | CSS Modules + design tokens (`src/styles/tokens.css`) |
| **Icons** | lucide-react |
| **HTTP Client** | Axios |
| **Markdown Rendering** | react-markdown, remark-gfm |
| **Charts** | Recharts |
| **i18n** | react-i18next (EN/VI) |
| **Linting** | ESLint |

## Project Structure

```text
frontend/
├── public/
│   └── locales/             # i18n translation files (en, vi)
└── src/
    ├── app/                 # Next.js App Router entry points
    │   ├── layout.tsx       # Root layout + providers
    │   ├── page.tsx         # Dashboard / entry screen
    │   ├── login/           # Login page
    │   ├── papers/          # Paper list & detail routes
    │   ├── profile/         # User profile
    │   ├── reports/         # Report listing & viewing
    │   ├── research/        # Active research session views
    │   ├── sessions/        # Session history listing
    │   └── providers.tsx    # React Query client, global context
    ├── components/
    │   ├── chat/            # Chat interface (messages, streaming, activity log)
    │   │   ├── ActivityLog/
    │   │   ├── ClaimsCard/
    │   │   ├── EvidenceCard/
    │   │   ├── PapersCollectedCard/
    │   │   ├── PlanCard/
    │   │   ├── StreamingText/
    │   │   ├── TaxonomyPreview/
    │   │   └── ThinkingBubble/
    │   ├── layout/          # Header, sidebar, app shell
    │   │   ├── AppShell/
    │   │   ├── Header/      # Includes LanguageSwitcher
    │   │   └── Sidebar/
    │   └── ui/              # Reusable UI primitives
    │       ├── Badge/
    │       ├── Button/
    │       ├── Card/
    │       ├── Input/
    │       ├── LanguageSwitcher/  # EN/VI language toggle
    │       ├── Modal/
    │       ├── Skeleton/
    │       └── Toast/
    ├── hooks/
    │   └── useResearchChat.ts  # Core SSE streaming hook (all real-time state)
    ├── lib/
    │   ├── constants.ts     # API base URL, app constants
    │   ├── i18n.ts          # i18n configuration (react-i18next)
    │   ├── types.ts         # TypeScript interfaces matching backend models
    │   └── utils.ts         # Utility functions (generateId, etc.)
    ├── services/
    │   └── conversations.ts # Axios-based API client for conversations
    └── styles/
        └── tokens.css       # Design tokens (colors, typography, spacing, glassmorphism)
```

## Key Architecture Details

### SSE Streaming (`useResearchChat.ts`)

The core hook manages all real-time communication with the backend:

- **Single SSE connection per conversation** — tracked via `connectedConvIdRef` to prevent duplicate connections
- **Handles all event types**: `progress`, `state_change`, `message`, `thinking`, `token_stream`, `plan`, `screening_summary`, `papers_collected`, `evidence`, `taxonomy`, `claims`, `gap_mining`, `approval_required`, `complete`, `done`, `result`, `error`
- **Token streaming**: Assembles `token_stream` events into complete messages with `isStreaming` flag
- **State change dedup**: Skips no-op transitions where `from === to`
- **Session restoration**: Loads existing session data (messages, activity log, pipeline status) on mount

### Type System (`lib/types.ts`)

All TypeScript interfaces mirror the backend Pydantic models:
- `SSEEvent` — discriminated union of all streaming event types
- `ChatEvent` — unified chat timeline entry (message, thinking, plan, evidence, etc.)
- `PipelineStatus` — current phase/progress
- `Paper`, `Claim`, `EvidenceSpan`, `TaxonomyMatrix` — research data models

### Internationalization

- Translation files: `public/locales/{en,vi}/common.json`
- Configuration: `src/lib/i18n.ts` using `react-i18next`
- Language switcher in the Header component

## Backend Integration

- Base URL: `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000/api/v1`)
- All HTTP calls go through the Axios instance in `src/services/conversations.ts`
- SSE stream URL: `{API_URL}/conversations/{id}/stream`

**Key endpoints used:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/conversations` | POST | Create new conversation |
| `/conversations` | GET | List all conversations |
| `/conversations/{id}` | GET | Get conversation state + messages |
| `/conversations/{id}/messages` | POST | Send message (returns 202, streams via SSE) |
| `/conversations/{id}/stream` | GET | SSE event stream |
| `/conversations/{id}` | DELETE | Delete conversation |

## Development Commands

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Start production build
npm start

# Lint
npm run lint
```

## Development Strategy

### Code Organization Principles

1. **Component-first UI** — Keep UI components small, focused, and reusable.
2. **Hooks for logic** — Place data fetching and non-trivial state logic into hooks in `src/hooks`.
3. **Single source of API truth** — Centralize all HTTP calls in `src/services` through a shared Axios instance.
4. **Type-safe** — Use TypeScript types/interfaces for API responses and component props.
5. **CSS Modules** — Component-scoped styles. Global CSS only for layout/theming via `tokens.css`.

### Common Patterns

**Extending SSE events:**
1. Add the event type to `SSEEvent` union in `lib/types.ts`
2. Add a handler `case` in `useResearchChat.ts` `connectSSE` switch
3. Expose new state via the hook's return object

**Adding new API calls:**
1. Add the service function in `src/services/conversations.ts`
2. Create a React Query hook in `src/hooks/` if needed
3. Use the hook in components — no raw Axios in components

## Known Issues & Notes

1. Authentication is not yet implemented in the frontend.
2. The `useResearchChat` hook manages all streaming state — avoid creating parallel SSE connections.
3. Backend must be running for the frontend to function (no mock/offline mode).
