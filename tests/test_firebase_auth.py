from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is not None:
            session.delete(user)
            session.commit()


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides.clear()
app.dependency_overrides[get_db] = _override_get_db


def test_me_requires_authorization() -> None:
    with TestClient(app) as client:
        response = client.get('/api/me')

    assert response.status_code == 401


def test_me_rejects_malformed_authorization() -> None:
    with TestClient(app) as client:
        response = client.get('/api/me', headers={'Authorization': 'Token abc123'})

    assert response.status_code == 401


def test_me_rejects_invalid_firebase_token(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    def fake_verify(token: str):
        raise ValueError('invalid token')

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/me', headers={'Authorization': 'Bearer invalid-token'})

    assert response.status_code == 401


def test_me_returns_existing_user_for_valid_token(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'existing-user-uid'
    _clear_user(firebase_uid)

    existing_user = User(
        firebase_uid=firebase_uid,
        email='existing@example.com',
        display_name='Existing User',
    )
    with SessionLocal() as session:
        session.add(existing_user)
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'existing@example.com', 'name': 'Existing User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/me', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['firebase_uid'] == firebase_uid
    assert payload['email'] == 'existing@example.com'
    assert payload['display_name'] == 'Existing User'


def test_me_creates_missing_user_and_does_not_duplicate(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'new-user-uid'
    _clear_user(firebase_uid)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'new@example.com', 'name': 'New User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        first = client.get('/api/me', headers={'Authorization': 'Bearer valid-token'})
        second = client.get('/api/me', headers={'Authorization': 'Bearer valid-token'})

    assert first.status_code == 200
    assert second.status_code == 200

    with SessionLocal() as session:
        users = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalars().all()
    assert len(users) == 1
    assert users[0].email == 'new@example.com'
    assert users[0].display_name == 'New User'


def test_me_syncs_email_and_display_name(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'sync-user-uid'
    _clear_user(firebase_uid)

    initial = User(firebase_uid=firebase_uid, email='old@example.com', display_name='Old Name')
    with SessionLocal() as session:
        session.add(initial)
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'new@example.com', 'name': 'Updated Name'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/me', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['email'] == 'new@example.com'
    assert payload['display_name'] == 'Updated Name'

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        assert user.email == 'new@example.com'
        assert user.display_name == 'Updated Name'
