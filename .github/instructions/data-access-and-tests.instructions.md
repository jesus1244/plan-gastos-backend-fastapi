---
applyTo: "app/**/*.py"
description: "Database access patterns, test expectations, and maintenance rules for the FastAPI backend."
---

# Data access and tests

## Database lifecycle

- MUST keep the database session scoped to the request and closed after use.
- SHOULD not leave a session open beyond the lifetime of a single request cycle.
- MUST commit explicit database mutations and roll back on integrity conflicts.
- SHOULD prefer clear error mapping for unique constraint violations and ownership mismatches.

## Testing standards

- MUST write tests for auth boundaries, ownership enforcement, duplicate-case handling, and mutation behavior.
- SHOULD use pytest fixtures and real app dependencies rather than relying on brittle mocks for core data-path logic.
- MUST verify that route behavior matches the user-facing contract, not internal implementation details.
- SHOULD test failure paths and not only the happy path.

## Maintenance

- SHOULD keep migrations explicit, reviewable, and tied to model changes.
- MUST avoid hidden schema drift between ORM models and Alembic revisions.
- SHOULD prefer a consistent naming convention for models, relationships, and route handlers.
- MUST keep the project maintainable for a small-to-medium team without introducing broad abstraction layers prematurely.
