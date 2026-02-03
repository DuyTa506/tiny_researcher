# Frontend Checklist

> **Checklist for Frontend AI Agent**.

## Phase 1: Setup & Design System
- [ ] **Init**: Create Next.js app, remove Tailwind configs (if existing).
- [ ] **Styles**: Define `globals.css` (Variables: `--primary`, `--bg`, `--text`...).
- [ ] **Icons**: Install `lucide-react`.
- [ ] **Query**: Setup `QueryClientProvider` (TanStack Query).

## Phase 2: UI Components (Base)
- [ ] **Button**: Primary/Secondary/Ghost variants (`Button.module.css`).
- [ ] **Input/Select**: Form elements.
- [ ] **Card**: Base container with Glassmorphism effect.
- [ ] **Layout**: Sidebar Navigation & Top Header.

## Phase 3: Screens & Logic

### Dashboard
- [ ] Layout grid.
- [ ] Stats Cards (Total Papers, New this week).

### Source Manager
- [ ] **List View**: Table of sources.
- [ ] **Add Source Modal**: Form validation (URL regex).
- [ ] **API**: Integrate `GET /sources` and `POST /sources`.

### Paper Workspace
- [ ] **Paper List**: Masonry/Grid layout.
- [ ] **Filters**: Date picker, Keyword search input.
- [ ] **Paper Detail**: Modal or Side-panel to read Abstract & Insights.
- [ ] **API**: Integrate `GET /papers`.

### Reporting
- [ ] **Report List**: History of generated reports.
- [ ] **Report Viewer**: Markdown renderer (use `react-markdown` or similar).

## Phase 4: Integration & Polish
- [ ] **Loading States**: Skeletons for clear UX.
- [ ] **Error Handling**: Toast notifications (Success/Error).
- [ ] **Responsive**: Verify Mobile/Tablet view.
- [ ] **Docker**: Build `Dockerfile` for production.
