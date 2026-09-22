"""Real, read-only adapters to Firestore and Firebase Auth for the migration CLI.

Only `.stream()` (Firestore) and `auth.get_user()` (Firebase Auth) are used —
both are read operations. Nothing here ever writes, deletes, or modifies
Firestore documents or Firebase Auth records.
"""

from __future__ import annotations

from collections.abc import Iterator

from firebase_admin import auth as firebase_auth_admin
from firebase_admin import firestore

from app.infrastructure.firebase_auth import initialize_firebase
from app.infrastructure.migration.migrator import FetchUsers, ResolveIdentity


def build_firestore_reader() -> FetchUsers:
    initialize_firebase()
    client = firestore.client()

    def fetch_users() -> Iterator[tuple[str, dict]]:
        for document in client.collection('users').stream():
            yield document.id, (document.to_dict() or {})

    return fetch_users


def build_identity_resolver() -> ResolveIdentity:
    initialize_firebase()

    def resolve_identity(firebase_uid: str) -> tuple[str | None, str | None]:
        try:
            record = firebase_auth_admin.get_user(firebase_uid)
        except Exception:
            return None, None
        return record.email, record.display_name

    return resolve_identity
