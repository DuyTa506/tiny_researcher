# Tiny Researcher Documentation

This branch contains the **code-first documentation** for the Tiny Researcher project, generated using the CodeWiki generator.

## What's Inside

Comprehensive VitePress documentation covering:

- **Architecture**: System design, component diagrams, dataflow
- **Getting Started**: Setup guides and quickstart
- **API Reference**: REST endpoints and WebSocket/SSE streaming
- **Domain Model**: Data entities and relationships
- **Performance**: Bottlenecks and scaling strategies
- **Integrations**: ArXiv, OpenAlex, OpenAI/Gemini APIs

## Quick Start

```bash
# Install dependencies
cd codewiki
npm install

# Run documentation site
npm run docs:dev

# Open http://localhost:5173
```

## Build for Production

```bash
cd codewiki
npm run docs:build
npm run docs:preview
```

## Features

- **Visual-First**: Mermaid diagrams throughout
- **Code Evidence**: Every claim backed by file references
- **Citation-First**: Explains the 10-phase research pipeline
- **19 Pages**: Comprehensive coverage of all major components

## Main Repository

For the full Tiny Researcher application code (backend, frontend, Docker setup), see the `main` branch:
- Backend: FastAPI Python application
- Frontend: Next.js React application
- Repository: https://github.com/DuyTa506/tiny_researcher

## Documentation Generator

Generated using the [codewiki-generator](https://github.com/anthropics/claude-code) skill for Claude Code.
