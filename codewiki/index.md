---
layout: home
hero:
  name: "Tiny Researcher"
  text: "AI-Powered Research Assistant"
  tagline: "Citation-grounded academic research automation from paper discovery to synthesis"
  actions:
    - theme: brand
      text: Getting Started
      link: /getting-started/quickstart
    - theme: alt
      text: Architecture
      link: /architecture/overview

features:
  - icon: 🔍
    title: "Multi-Source Search"
    details: "Parallel search across ArXiv and OpenAlex with intelligent 4-level deduplication (DOI, ArXiv ID, fingerprint, title similarity)"
  - icon: ⚡
    title: "10-Phase Citation-First Pipeline"
    details: "Systematic screening, evidence extraction with page locators, claim generation, citation audit, and gap mining"
  - icon: 📊
    title: "Grounded Synthesis"
    details: "Every claim backed by verbatim evidence spans with page-level citations. LLM judge audits and auto-repairs claims."
  - icon: 🎯
    title: "HITL Approval Gates"
    details: "Human-in-the-loop approval for PDF downloads, external URLs, and token budgets to control costs and quality"
  - icon: 🧩
    title: "Adaptive Planning"
    details: "Automatically selects QUICK or FULL mode based on query type. Generates search strategies with LLM-powered query refinement."
  - icon: 🌐
    title: "Modern Full-Stack"
    details: "FastAPI backend with async MongoDB/Redis, Next.js 16 frontend with SSE streaming, React Query, and i18n (EN/VI)"
---

## Tech Stack Overview

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 16, React 19, TypeScript | Interactive research workspace with SSE streaming |
| **Backend** | FastAPI, Python 3.11, Pydantic v2 | Async API and pipeline orchestration |
| **Database** | MongoDB (Motor), Redis | Document storage and caching (3-tier: hot/warm/cold) |
| **LLM** | OpenAI GPT-4, Google Gemini | Planning, extraction, synthesis, audit |
| **Vector Store** | Qdrant | Semantic embeddings for clustering |
| **Search APIs** | ArXiv API, OpenAlex API | Academic paper sources |
| **PDF Processing** | PyMuPDF, pypdf | Full-text extraction with page mapping |

## Quick Navigation

- [Quickstart Guide](/getting-started/quickstart) - Get up and running in 5 minutes
- [Architecture Overview](/architecture/overview) - System design and component interactions
- [Core Components](/core-components/overview) - Service responsibilities and relationships
- [Development Guide](/development/overview) - Local setup, testing, debugging
- [API Reference](/api-reference/overview) - REST endpoints and WebSocket streams
- [Data Model](/data/domain-model) - Entity relationships and schemas
- [Performance](/performance/bottlenecks) - Known bottlenecks and scaling strategies

## Key Differentiators

**Citation-First Workflow**: Unlike traditional academic literature review tools, Tiny Researcher enforces citation traceability at every step. Every claim in the final report is linked to specific evidence spans with page-level locators, and an LLM judge audits all citations before publishing.

**Multi-Source Deduplication**: Parallel search across ArXiv and OpenAlex with sophisticated 4-level deduplication prevents redundant processing and ensures comprehensive coverage.

**Human-in-the-Loop Gates**: HITL approval gates for PDF downloads and token budgets give researchers control over costs while maintaining automation benefits.

**Adaptive Execution**: Query-aware planning automatically selects QUICK mode for concept checks or FULL mode for comprehensive literature reviews, optimizing time and resources.

## Repository Structure

```
tiny_researcher/
├── backend/              # Python FastAPI application
│   ├── src/
│   │   ├── api/         # REST routes (auth, papers, reports, conversations)
│   │   ├── research/    # Pipeline (10-phase citation-first + legacy 8-phase)
│   │   ├── planner/     # Adaptive planning and execution
│   │   ├── storage/     # MongoDB repositories (8 collections)
│   │   ├── tools/       # Search tools (ArXiv, OpenAlex, URL collection)
│   │   └── core/        # Models, config, prompts
│   └── docs/            # Backend documentation
├── frontend/            # Next.js application
│   ├── src/
│   │   ├── app/        # App Router pages
│   │   ├── components/ # Chat UI, cards, layout
│   │   ├── hooks/      # useResearchChat SSE hook
│   │   └── services/   # Axios API clients
│   └── public/locales/ # i18n translations (EN/VI)
└── nginx/              # Reverse proxy configuration
```

## Getting Help

- **New to the project?** Start with the [Quickstart Guide](/getting-started/quickstart)
- **Understanding the architecture?** See [Architecture Overview](/architecture/overview)
- **Local development?** Check [Development Guide](/development/overview)
- **API integration?** Read [API Reference](/api-reference/overview)
