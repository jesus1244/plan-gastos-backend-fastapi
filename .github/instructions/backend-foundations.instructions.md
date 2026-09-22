---
applyTo: "**/*.py"
description: "Python, FastAPI, Pydantic, and SQLAlchemy baseline standards for the backend."
---

# Backend foundations

## Python and typing

- MUST target Python 3.11+ and keep code compatible with the project minimum.
- MUST prefer explicit function signatures and typed return values.
- MUST avoid `Any` unless there is a narrow and explained reason.
- SHOULD use `Annotated` for shared FastAPI dependencies when it improves readability and keeps models consistent.
- SHOULD prefer `| None` and explicit guards over implicit truthiness checks when values may be absent.

## FastAPI and Pydantic

- MUST define request and response schemas with Pydantic models instead of blindly accepting raw payloads.
- MUST use `response_model` and explicit status codes to make API contracts clear.
- SHOULD prefer validation on the schema boundary and keep routes free of ad hoc parsing logic.
- MUST raise `HTTPException` with meaningful `status_code` and `detail` values rather than returning inconsistent dicts.
- MUST prefer a single, predictable error-handling strategy across the API surface.

## SQLAlchemy and data access

- MUST use SQLAlchemy 2.x idioms consistently with `select(...)`, typed ORM models, and explicit session lifecycle.
- MUST keep ORM model definitions and query logic readable and domain-specific.
- SHOULD keep query logic close to the feature it serves unless a clear reuse boundary exists.
- MUST avoid silently bypassing ownership and foreign-key checks in route code.
- SHOULD ensure each mutation path validates that the target record belongs to the current authenticated user.

## Project boundaries

- MUST keep route modules focused on request/response orchestration.
- SHOULD keep domain logic close to the feature or model it impacts, not hidden in generic abstractions.
- MUST avoid creating top-level “common” service layers for every repeated pattern until there is a demonstrable maintenance need.
- SHOULD prefer explicit helper functions for repeated ownership checks only when they clearly belong to a feature scope and are not duplicated across unrelated modules.
