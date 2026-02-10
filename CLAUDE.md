# Tiny Researcher Project Overview

## Project Description

**Tiny Researcher** is an advanced AI agent workspace designed for comprehensive academic research. It automates the process of paper discovery, evidence extraction, and synthesis into grounded reports.

**Core Workflow:**
1.  **Clarify & Plan**: Refines research questions and generates a step-by-step plan.
2.  **Collect & Screen**: Aggregates papers from Arxiv/PubMed, deduplicates, and filters by relevance.
3.  **Extract & Synthesize**: Loads full-text PDFs, extracts key evidence, clusters findings, and generates a final report with citations.

The project is structured as a modern full-stack application with a Python FastAPI backend for heavy lifting (LLM orchestration, vector search) and a Next.js frontend for the interactive research workspace.

## Complete Tech Stack

| Category | Technology | Description |
|----------|------------|-------------|
| **Backend Framework** | FastAPI | High-performance web framework for building APIs with Python 3.11+, featuring automatic interactive documentation (OpenAPI). |
| **Frontend Framework** | Next.js 16.1 | React framework for building full-stack web applications, featuring App Router and Server Components. |
| **Language** | Python / TypeScript | Backend logic in Python; Frontend interface in TypeScript. |
| **Database** | MongoDB (Motor) | Asynchronous MongoDB driver for Python, handling document storage. |
| **Task Queue** | Celery + Redis | Distributed task queue for handling long-running research jobs (scraping, LLM processing). |
| **LLM Orchestration** | LangChain / OpenAI / Gemini | Integration with GPT-4 and Gemini Pro for reasoning and generation. |
| **Research Tools** | Arxiv, BioPython | Libraries for accessing academic repositories. |
| **NLP & ML** | Spacy, Scikit-learn, Sentence-Transformers | For text processing, clustering, and embedding generation. |
| **State Management** | React Query (@tanstack/react-query) | Server state management for reacting to async data changes. |
| **Styling** | CSS Modules + Global CSS | Scoped styling for components and global theme definitions. |
| **Icons** | Lucide React | Consistent and clean icon set. |
| **Testing** | Pytest, Vitest | Backend and Frontend testing frameworks. |

## Complete Project Structure

Monorepo structure separating the `backend` services from the `frontend` application.

```
tiny_researcher/
├── backend/                     # Python FastAPI Application
│   ├── src/
│   │   ├── adapters/            # External service adapters (Arxiv, etc.)
│   │   ├── api/                 # FastAPI routes and controllers
│   │   ├── cli/                 # Command-line interface tools
│   │   ├── conversation/        # Chat and history management
│   │   ├── core/                # Core configuration and types
│   │   ├── memory/              # Vector storage and retrieval logic
│   │   ├── planner/             # Research planning modules
│   │   ├── research/            # Core research pipeline logic
│   │   ├── storage/             # Database connection handling
│   │   ├── tools/               # LLM Tools (Search, Scrape, etc.)
│   │   ├── utils/               # Helper functions
│   │   └── workers/             # Celery worker definitions
│   ├── tests/                   # Pytest suite
│   ├── docker/                  # Docker configuration files
│   ├── pyproject.toml           # Poetry dependency management
│   └── requirements.txt         # Pip requirements
├── frontend/                    # Next.js Application
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   │   ├── (routes)/
│   │   │   ├── papers/          # Paper listing and details
│   │   │   ├── reports/         # Report generation views
│   │   │   └── research/        # Active research session views
│   │   ├── components/          # React components
│   │   │   ├── chat/            # Chat interface components
│   │   │   ├── layout/          # Layout wrappers
│   │   │   └── ui/              # Reusable UI elements
│   │   ├── hooks/               # Custom React hooks
│   │   ├── lib/                 # Utilities and constants
│   │   └── services/            # API client services
│   ├── public/                  # Static assets
│   ├── next.config.ts           # Next.js configuration
│   └── package.json             # Node dependencies
├── .agents/                     # Agentic workflows and skills
└── .gitignore                   # Git ignore rules
```

## Architecture Map

| Layer | Location | Description |
|-------|----------|-------------|
| **UI Components** | `frontend/src/components` | Reusable UI library and feature-specific components. |
| **Pages/Routing** | `frontend/src/app` | Next.js App Router handling navigation and server-side rendering. |
| **Client State** | `frontend/src/app/providers.tsx` | React Query Client provider for caching and state syncing. |
| **API Client** | `frontend/src/services` | Axios wrappers interacting with the Backend API. |
| **API Gateway** | `backend/src/api` | FastAPI routers exposing REST endpoints. |
| **Core Logic** | `backend/src/research` | The "brain" of the researcher; handles the pipeline phases. |
| **Async Workers** | `backend/src/workers` | Celery tasks for parallel processing (summarization, scraping). |
| **Data Access** | `backend/src/storage` | Abstraction layer for MongoDB interactions. |
| **Vector Memory** | `backend/src/memory` | Handling semantic search and embeddings (Qdrant/Local). |
| **External APIs** | `backend/src/adapters` | Interfaces for Arxiv, PubMed, OpenAI, etc. |

## Data Flow

```mermaid
graph TD
    User[User] -->|Interacts| UI[Frontend UI (Next.js)]
    UI -->|API Requests| API[Backend API (FastAPI)]
    
    subgraph "Backend Services"
        API -->|Dispatch| Planner[Planner Module]
        API -->|Enqueue| Queue[Celery Task Queue]
        
        Queue -->|Process| Worker[Worker Nodes]
        Worker -->|Fetch| Ext[External Sources (Arxiv/Web)]
        Worker -->|LLM Call| LLM[LLM Provider (OpenAI/Gemini)]
        
        Planner -->|Store/Retrieve| DB[(MongoDB)]
        Worker -->|Store/Retrieve| DB
        
        Worker -->|Embed| Vector[(Vector Store)]
    end
    
    subgraph "Research Pipeline"
        Plan --> Collect --> Extract --> Cluster --> Synthesize
    end
    
    Worker -.-> Pipeline -.-> API
    API -->|SSE/Stream| UI
```
