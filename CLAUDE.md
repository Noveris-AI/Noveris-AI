# Noveris-AI Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-16

## 重要说明

**必须使用中文回复所有问题和交流。All responses must be in Chinese.**

## Active Technologies
- Python 3.11+ + FastAPI 0.109+, SQLAlchemy 2.0.25+, Redis 5.0+, Pydantic 2.5+, Passlib (bcrypt), Structlog (003-auth-refactor)
- PostgreSQL (用户数据) + Redis (会话存储) (003-auth-refactor)

- Backend: Python 3.11; Frontend: TypeScript 5.2.2 + React 18.2.0 + Backend: FastAPI 0.109.0+, SQLAlchemy 2.0.25+, Alembic 1.13.0; Frontend: React Router 6.20.1, TanStack React Query 5.17.15, Axios 1.13.2, Zod 3.22.4 (001-node-management-integration)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Backend: Python 3.11; Frontend: TypeScript 5.2.2 + React 18.2.0: Follow standard conventions

## Recent Changes
- 003-auth-refactor: Added Python 3.11+ + FastAPI 0.109+, SQLAlchemy 2.0.25+, Redis 5.0+, Pydantic 2.5+, Passlib (bcrypt), Structlog
- 002-auth-integration: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

- 001-node-management-integration: Added Backend: Python 3.11; Frontend: TypeScript 5.2.2 + React 18.2.0 + Backend: FastAPI 0.109.0+, SQLAlchemy 2.0.25+, Alembic 1.13.0; Frontend: React Router 6.20.1, TanStack React Query 5.17.15, Axios 1.13.2, Zod 3.22.4

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
