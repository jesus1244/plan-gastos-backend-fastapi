from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, OvertimeEntry, User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user_data(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is not None:
            budget_ids = [budget.id for budget in session.execute(select(Budget).where(Budget.user_id == user.id)).scalars().all()]
            if budget_ids:
                session.query(OvertimeEntry).filter(OvertimeEntry.budget_id.in_(budget_ids)).delete(synchronize_session=False)
                session.query(Budget).filter(Budget.id.in_(budget_ids)).delete(synchronize_session=False)
            session.delete(user)
            session.commit()


def _create_budget(firebase_uid: str) -> str:
    _clear_user_data(firebase_uid)
    with SessionLocal() as session:
        user = User(firebase_uid=firebase_uid, email=f'{firebase_uid}@example.com', display_name='Test User')
        session.add(user)
        session.flush()
        budget = Budget(user_id=user.id, name='September', month_key='2026-09', base_salary=Decimal('3000000'))
        session.add(budget)
        session.commit()
        return budget.id


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides.clear()
app.dependency_overrides[get_db] = _override_get_db


def _auth(monkeypatch, firebase_uid: str) -> None:
    from app.infrastructure import firebase_auth

    monkeypatch.setattr(
        firebase_auth,
        'verify_firebase_token',
        lambda token: {'uid': firebase_uid, 'email': f'{firebase_uid}@example.com', 'name': 'Test User'},
    )


def _payload() -> dict[str, object]:
    return {
        'date': '2026-09-07',
        'hours': '3.50',
        'type': 'ordinary',
        'shift': 'night',
        'start_time': '18:00:00',
        'end_time': '21:30:00',
        'description': 'Integration work',
    }


def test_detailed_overtime_crud_and_multiple_entries(monkeypatch) -> None:
    firebase_uid = 'detailed-overtime-user'
    budget_id = _create_budget(firebase_uid)
    _auth(monkeypatch, firebase_uid)

    with TestClient(app) as client:
        first = client.post(f'/api/budgets/{budget_id}/overtime', json=_payload(), headers={'Authorization': 'Bearer token'})
        second = client.post(
            f'/api/budgets/{budget_id}/overtime',
            json={**_payload(), 'date': '2026-09-08', 'hours': '2.00', 'type': 'sunday', 'shift': 'day'},
            headers={'Authorization': 'Bearer token'},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    first_payload = first.json()
    assert first_payload['budget_id'] == budget_id
    assert first_payload['hours'] == '3.50'
    assert first_payload['description'] == 'Integration work'

    entry_id = first_payload['id']
    with TestClient(app) as client:
        listed = client.get(f'/api/budgets/{budget_id}/overtime', headers={'Authorization': 'Bearer token'})
        fetched = client.get(f'/api/budgets/{budget_id}/overtime/{entry_id}', headers={'Authorization': 'Bearer token'})
        updated = client.put(
            f'/api/budgets/{budget_id}/overtime/{entry_id}',
            json={**_payload(), 'hours': '4.00', 'description': 'Updated'},
            headers={'Authorization': 'Bearer token'},
        )
        deleted = client.delete(f'/api/budgets/{budget_id}/overtime/{entry_id}', headers={'Authorization': 'Bearer token'})
        missing = client.get(f'/api/budgets/{budget_id}/overtime/{entry_id}', headers={'Authorization': 'Bearer token'})

    assert [entry['date'] for entry in listed.json()] == ['2026-09-07', '2026-09-08']
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert updated.json()['hours'] == '4.00'
    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_overtime_ownership_and_validation(monkeypatch) -> None:
    owner_budget = _create_budget('overtime-owner')
    other_budget = _create_budget('overtime-other')
    _auth(monkeypatch, 'overtime-owner')

    with TestClient(app) as client:
        invalid = client.post(
            f'/api/budgets/{owner_budget}/overtime',
            json={**_payload(), 'hours': '-1'},
            headers={'Authorization': 'Bearer token'},
        )
        foreign = client.get(f'/api/budgets/{other_budget}/overtime', headers={'Authorization': 'Bearer token'})
        missing_budget = client.get('/api/budgets/00000000-0000-0000-0000-000000000000/overtime', headers={'Authorization': 'Bearer token'})

    assert invalid.status_code == 422
    assert foreign.status_code == 404
    assert missing_budget.status_code == 404


def test_overtime_requires_time_pair(monkeypatch) -> None:
    budget_id = _create_budget('overtime-time-pair')
    _auth(monkeypatch, 'overtime-time-pair')

    with TestClient(app) as client:
        response = client.post(
            f'/api/budgets/{budget_id}/overtime',
            json={**_payload(), 'end_time': None},
            headers={'Authorization': 'Bearer token'},
        )

    assert response.status_code == 422
