---
applyTo: "app/**/*.py"
description: "Authentication, Firebase verification, and secure backend practices for the API."
---

# Security and authentication

## Firebase auth

- MUST treat Firebase ID tokens as the trust boundary for authenticated requests.
- MUST verify the token server-side before granting access to protected endpoints.
- SHOULD keep Firebase initialization and token verification logic in a dedicated auth/infrastructure module.
- MUST reject missing, malformed, or invalid `Authorization: Bearer <token>` headers with `401 Unauthorized`.
- MUST avoid trusting unverified user claims passed by the client.

## User sync and ownership

- MUST ensure a user is created or synchronized based on the verified Firebase UID.
- MUST use the authenticated user identity to scope database access to that user’s records.
- SHOULD avoid mixing user identity from the request body with the identity from the validated token.
- MUST ensure resources are retrieved by both resource ID and ownership constraints when user-scoped APIs are involved.

## Configuration and secrets

- MUST keep secrets in environment variables or a secure secret manager, not in code.
- MUST validate Firebase service-account configuration before trying to initialize the SDK.
- SHOULD fail fast with a clear configuration error when required Firebase values are missing.
- MUST avoid logging sensitive authentication material or raw private keys.
