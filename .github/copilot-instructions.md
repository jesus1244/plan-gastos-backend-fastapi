---
applyTo: "**/*.py"
---

# Copilot instructions for this FastAPI backend

This repository is a Python FastAPI backend for the Plan Gastos application. Follow these rules before generating or changing code.

## Mandatory workflow

- MUST inspect the current backend structure, route boundaries, and data model before making changes.
- MUST respect the existing domain shape and naming conventions before introducing new patterns.
- MUST prefer the smallest solution that fits the current project size and complexity.
- MUST verify framework and library compatibility before using any FastAPI, Pydantic, SQLAlchemy, or Firebase guidance.
- MUST avoid broad refactors unrelated to the requested task.
- MUST keep the change scope narrow and aligned with the user request.

## FastAPI baseline

- MUST use FastAPI official guidance as the source of truth.
- MUST prefer dependency injection via `Depends` for auth and database access when it reduces repetition.
- MUST prefer explicit request/response schemas with Pydantic v2 models over ad hoc dict payloads.
- MUST prefer SQLAlchemy 2.x patterns with clear model ownership and explicit session boundaries.
- MUST keep route functions focused on request handling, validation, and orchestration rather than embedding business logic scattered across modules.
- MUST not add heavy architectural abstractions when a small project can be maintained with clear modules and explicit contracts.
- MUST not add a new library when FastAPI, Pydantic, or SQLAlchemy already provide the needed capability.

## Quality gate

- MUST NOT use `Any` in new application code unless there is a narrowly justified and documented exception.
- MUST NOT suppress typing issues with broad casts or unsafe assertions.
- MUST NOT invent generic `utils`, `helpers`, or `common` modules that hide unrelated responsibilities.
- MUST NOT add enterprise-level abstractions for simple CRUD flows unless the project clearly needs them.
- MUST NOT duplicate ownership-check or CRUD logic across multiple route modules.
- MUST NOT add comments that restate obvious code; comments are only for non-obvious decisions or behavior.
- MUST keep functions and modules small, focused, and easy to test.

## When working in this repo

- MUST keep feature logic in proper domain boundaries: routes, schemas, models, and infrastructure.
- SHOULD prefer feature-local services or shared service functions over cross-cutting singleton layers when the scope is limited to one feature.
- SHOULD keep presentation concerns out of persistence code and keep route logic explicit.
- SHOULD use typed DTOs and explicit contracts for API payloads and external boundaries.
- SHOULD write tests for real behavior, especially auth, ownership, and mutation paths.

## Detailed guidance

The repo-level instruction set is organized into targeted guidance files under [.github/instructions](instructions). Follow the most relevant file for the task.

The detailed rules are intentionally strict and are designed to reduce common FastAPI anti-patterns, weak validation, duplicated DB logic, and unnecessary abstraction.
