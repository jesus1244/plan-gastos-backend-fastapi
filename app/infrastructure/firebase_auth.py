from __future__ import annotations

import logging
from typing import Any

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.config import settings
from app.infrastructure.database.dependencies import get_db
from app.infrastructure.database.models.user import User

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def _build_firebase_credentials() -> dict[str, str]:
    project_id = settings.firebase_project_id or None
    client_email = settings.firebase_client_email or None
    private_key = settings.firebase_private_key or None

    if not project_id and not client_email and not private_key:
        return {}

    if not project_id or not client_email or not private_key:
        raise ValueError('Firebase configuration is incomplete. Set FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, and FIREBASE_PRIVATE_KEY.')

    return {
        'type': 'service_account',
        'project_id': project_id,
        'client_email': client_email,
        'private_key': private_key.replace('\\n', '\n'),
        'token_uri': 'https://oauth2.googleapis.com/token'
    }


def initialize_firebase() -> None:
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    credentials_payload = _build_firebase_credentials()
    if not credentials_payload:
        return

    cred = firebase_admin.credentials.Certificate(credentials_payload)

    firebase_admin.initialize_app(cred)

def verify_firebase_token(token: str) -> dict[str, Any]:
    initialize_firebase()
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except (ValueError, FirebaseError):
        raise


def _get_or_create_user(db: Session, firebase_uid: str, email: str | None, display_name: str | None) -> User:
    stmt = select(User).where(User.firebase_uid == firebase_uid)
    user = db.execute(stmt).scalar_one_or_none()

    if user is not None:
        update_needed = False
        if email and user.email != email:
            user.email = email
            update_needed = True
        if display_name is not None and user.display_name != display_name:
            user.display_name = display_name
            update_needed = True
        if update_needed:
            db.commit()
        return user

    new_user = User(
        firebase_uid=firebase_uid,
        email=email or f'{firebase_uid}@firebase.local',
        display_name=display_name,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        user = db.execute(stmt).scalar_one()
        return user
    db.refresh(new_user)
    return new_user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != 'bearer' or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

    token = credentials.credentials
    try:
        decoded_token = verify_firebase_token(token)
    except (ValueError, FirebaseError) as exc:
        logger.warning('Rejected invalid Firebase token: %s', exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized') from None

    firebase_uid = decoded_token.get('uid')
    email = decoded_token.get('email')
    display_name = decoded_token.get('name') or decoded_token.get('display_name')

    if not firebase_uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')

    user = _get_or_create_user(db, firebase_uid, email, display_name)
    return user
