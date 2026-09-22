---
applyTo: "app/api/**/*.py"
description: "Route design, ownership checks, and API contract rules for FastAPI endpoints."
---

# API route structure

## Routing and dependency injection

- MUST define routes with clear prefixes and resource-oriented naming.
- MUST prefer `Depends(get_current_user)` and `Depends(get_db)` as the default dependency pattern for authenticated endpoints.
- SHOULD avoid repeating the same auth and session setup logic in every route when a shared dependency boundary already exists.
- MUST keep route parameters explicit and typed to preserve OpenAPI clarity.
- SHOULD use `Annotated` aliases for repeated dependencies when the codebase uses them widely.

## Ownership boundaries

- MUST enforce ownership checks before reading, updating, or deleting a resource tied to a budget or user.
- MUST reject access to foreign resources with `404` or the equivalent not-found semantics rather than leaking information.
- SHOULD centralize “budget belongs to current user” logic in a single explicit helper when repeated across multiple routes.
- MUST NOT trust the client to supply a valid `user_id` or `budget_id` when the database ownership check is required.

## Mutations and responses

- MUST return response models for successful reads and writes.
- MUST use clear status codes for create, update, and delete flows.
- SHOULD prefer a consistent pattern for duplicate conflict handling and validation errors.
- MUST keep route functions short and readable; complex business rules should move to a typed service or domain function when the logic grows.
