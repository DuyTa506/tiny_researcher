# Research Assistant Backend

## Overview
Modular, microservices-oriented framework for AI research assistance.

## Project Structure
Uses Hexagonal Architecture (Ports & Adapters).
- `src/core`: Domain models & config
- `src/services`: Business logic
- `src/adapters`: External integrations
- `src/api`: FastAPI endpoints

## Getting Started

1. **Install Dependencies**
   ```bash
   poetry install
   ```

2. **Environment**
   ```bash
   cp .env.example .env
   ```

3. **Run with Docker**
   ```bash
   cd docker
   docker-compose up --build
   ```

4. **Run Locally**
   ```bash
   docker-compose up -d postgres redis qdrant
   poetry run uvicorn src.api.main:app --reload
   ```

## Documentation
- [Agent Guide](./agent_guide.md)
- [System Design](./system_design.md)
