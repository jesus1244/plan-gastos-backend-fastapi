"""Administrative entry point for the Fase 21 migration.

Usage:
    python -m app.infrastructure.migration [--dry-run]
"""

from __future__ import annotations

import argparse

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.migration.firestore_reader import build_firestore_reader, build_identity_resolver
from app.infrastructure.migration.migrator import FirestoreMigrator


def main() -> None:
    parser = argparse.ArgumentParser(description='Migrate legacy Firestore budgets into PostgreSQL (read-only on Firestore).')
    parser.add_argument('--dry-run', action='store_true', help='Validate and report without writing to PostgreSQL.')
    args = parser.parse_args()

    session = SessionLocal()
    try:
        migrator = FirestoreMigrator(
            session=session,
            fetch_users=build_firestore_reader(),
            resolve_identity=build_identity_resolver(),
            dry_run=args.dry_run,
        )
        summary = migrator.run()
    finally:
        session.close()

    print(summary.report(dry_run=args.dry_run))


if __name__ == '__main__':
    main()
