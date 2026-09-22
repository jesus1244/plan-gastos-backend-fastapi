from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, Overtime, User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user_data(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is None:
            return
        for budget in list(user.budgets):
            if budget.overtime is not None:
                session.delete(budget.overtime)
            session.delete(budget)
        session.delete(user)
        session.commit()


def _create_user(firebase_uid: str, email: str, display_name: str) -> str:
    _clear_user_data(firebase_uid)
    with SessionLocal() as session:
        user = User(firebase_uid=firebase_uid, email=email, display_name=display_name)
        session.add(user)
        session.commit()
        session.refresh(user)
        return str(user.id)


def _create_budget(user_id: str, month_key: str, name: str = 'Budget') -> str:
    with SessionLocal() as session:
        budget = Budget(user_id=user_id, name=name, month_key=month_key, base_salary=Decimal('3000000'))
        session.add(budget)
        session.commit()
        session.refresh(budget)
        return str(budget.id)


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides.clear()
app.dependency_overrides[get_db] = _override_get_db


def test_get_without_token_fails() -> None:
    with TestClient(app) as client:
        response = client.get('/api/budgets/123/overtime')
    assert response.status_code == 401


def test_put_without_token_fails() -> None:
    with TestClient(app) as client:
        response = client.put(
            '/api/budgets/123/overtime',
            json={'ordinary_day_hours': 8, 'ordinary_night_hours': 2, 'sunday_day_hours': 4, 'sunday_night_hours': 1},
        )
    assert response.status_code == 401


def test_delete_without_token_fails() -> None:
    with TestClient(app) as client:
        response = client.delete('/api/budgets/123/overtime')
    assert response.status_code == 401


def test_invalid_token_is_rejected(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    def fake_verify(token: str):
        raise ValueError('bad token')

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/budgets/123/overtime', headers={'Authorization': 'Bearer bad-token'})

    assert response.status_code == 401


def test_get_overtime_returns_existing_record(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'overtime-user-get'
    _create_user(firebase_uid, 'overtimeget@example.com', 'Overtime Get User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-01', 'Get Budget')
        overtime = Overtime(
            budget_id=budget_id,
            ordinary_day_hours=Decimal('8.00'),
            ordinary_night_hours=Decimal('2.50'),
            sunday_day_hours=Decimal('4.00'),
            sunday_night_hours=Decimal('1.00'),
        )
        session.add(overtime)
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'overtimeget@example.com', 'name': 'Overtime Get User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/overtime', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert payload['ordinary_day_hours'] == '8.00'
    assert payload['ordinary_night_hours'] == '2.50'
    assert payload['budget_id'] == budget_id


def test_get_overtime_returns_404_for_missing_budget_or_overtime(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'overtime-user-missing'
    _create_user(firebase_uid, 'overtimemissing@example.com', 'Missing User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-02', 'Missing Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'overtimemissing@example.com', 'name': 'Missing User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        missing_overtime = client.get(f'/api/budgets/{budget_id}/overtime', headers={'Authorization': 'Bearer valid-token'})
        missing_budget = client.get('/api/budgets/00000000-0000-0000-0000-000000000000/overtime', headers={'Authorization': 'Bearer valid-token'})

    assert missing_overtime.status_code == 404
    assert missing_budget.status_code == 404


def test_put_creates_and_replaces_overtime_in_one_to_one_relation(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'overtime-user-put'
    _create_user(firebase_uid, 'overtimeput@example.com', 'Overtime Put User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-03', 'Put Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'overtimeput@example.com', 'name': 'Overtime Put User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    payload = {
        'ordinary_day_hours': 8,
        'ordinary_night_hours': 2,
        'sunday_day_hours': 4,
        'sunday_night_hours': 1,
    }

    with TestClient(app) as client:
        created = client.put(f'/api/budgets/{budget_id}/overtime', json=payload, headers={'Authorization': 'Bearer valid-token'})
        replaced = client.put(
            f'/api/budgets/{budget_id}/overtime',
            json={**payload, 'ordinary_day_hours': 6, 'ordinary_night_hours': 1},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert created.status_code == 200
    assert replaced.status_code == 200

    with SessionLocal() as session:
        overtime = session.execute(select(Overtime).where(Overtime.budget_id == budget_id)).scalar_one()
        assert overtime.ordinary_day_hours == Decimal('6.00')
        assert overtime.ordinary_night_hours == Decimal('1.00')
        assert overtime.sunday_day_hours == Decimal('4.00')
        assert overtime.sunday_night_hours == Decimal('1.00')


def test_put_rejects_budget_id_in_body(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'overtime-user-body'
    _create_user(firebase_uid, 'overtimebody@example.com', 'Body User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-04', 'Body Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'overtimebody@example.com', 'name': 'Body User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.put(
            f'/api/budgets/{budget_id}/overtime',
            json={'budget_id': 'another-id', 'ordinary_day_hours': 8, 'ordinary_night_hours': 2, 'sunday_day_hours': 4, 'sunday_night_hours': 1},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 422


def test_put_validates_negative_hours_and_required_fields(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'overtime-user-validations'
    _create_user(firebase_uid, 'overtimevalid@example.com', 'Validation User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-05', 'Validation Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'overtimevalid@example.com', 'name': 'Validation User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        negative = client.put(
            f'/api/budgets/{budget_id}/overtime',
            json={'ordinary_day_hours': -1, 'ordinary_night_hours': 2, 'sunday_day_hours': 4, 'sunday_night_hours': 1},
            headers={'Authorization': 'Bearer valid-token'},
        )
        missing = client.put(
            f'/api/budgets/{budget_id}/overtime',
            json={'ordinary_day_hours': 8, 'ordinary_night_hours': 2, 'sunday_day_hours': 4},
            headers={'Authorization': 'Bearer valid-token'},
        )
        invalid_value = client.put(
            f'/api/budgets/{budget_id}/overtime',
            json={'ordinary_day_hours': 'bad', 'ordinary_night_hours': 2, 'sunday_day_hours': 4, 'sunday_night_hours': 1},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert negative.status_code == 422
    assert missing.status_code == 422
    assert invalid_value.status_code == 422


def test_ownership_blocks_access_to_other_users_overtime(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    user_a_uid = 'overtime-user-a'
    user_b_uid = 'overtime-user-b'
    _create_user(user_a_uid, 'a@example.com', 'User A')
    _create_user(user_b_uid, 'b@example.com', 'User B')

    with SessionLocal() as session:
        user_a = session.execute(select(User).where(User.firebase_uid == user_a_uid)).scalar_one()
        user_b = session.execute(select(User).where(User.firebase_uid == user_b_uid)).scalar_one()
        budget_a_id = _create_budget(str(user_a.id), '2026-06', 'Budget A')
        budget_b_id = _create_budget(str(user_b.id), '2026-07', 'Budget B')
        overtime_b = Overtime(
            budget_id=budget_b_id,
            ordinary_day_hours=Decimal('9.00'),
            ordinary_night_hours=Decimal('2.00'),
            sunday_day_hours=Decimal('5.00'),
            sunday_night_hours=Decimal('1.00'),
        )
        session.add(overtime_b)
        session.commit()

    def fake_verify(token: str):
        return {'uid': user_a_uid, 'email': 'a@example.com', 'name': 'User A'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        get_response = client.get(f'/api/budgets/{budget_b_id}/overtime', headers={'Authorization': 'Bearer valid-token'})
        put_response = client.put(
            f'/api/budgets/{budget_b_id}/overtime',
            json={'ordinary_day_hours': 8, 'ordinary_night_hours': 2, 'sunday_day_hours': 4, 'sunday_night_hours': 1},
            headers={'Authorization': 'Bearer valid-token'},
        )
        delete_response = client.delete(f'/api/budgets/{budget_b_id}/overtime', headers={'Authorization': 'Bearer valid-token'})

    assert get_response.status_code == 404
    assert put_response.status_code == 404
    assert delete_response.status_code == 404


def test_delete_overtime_and_repeated_delete_returns_404(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'overtime-user-delete'
    _create_user(firebase_uid, 'overtimedelete@example.com', 'Delete User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-08', 'Delete Budget')
        overtime = Overtime(
            budget_id=budget_id,
            ordinary_day_hours=Decimal('8.00'),
            ordinary_night_hours=Decimal('2.00'),
            sunday_day_hours=Decimal('4.00'),
            sunday_night_hours=Decimal('1.00'),
        )
        session.add(overtime)
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'overtimedelete@example.com', 'name': 'Delete User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        delete_response = client.delete(f'/api/budgets/{budget_id}/overtime', headers={'Authorization': 'Bearer valid-token'})
        get_after_delete = client.get(f'/api/budgets/{budget_id}/overtime', headers={'Authorization': 'Bearer valid-token'})
        delete_again = client.delete(f'/api/budgets/{budget_id}/overtime', headers={'Authorization': 'Bearer valid-token'})

    assert delete_response.status_code == 204
    assert get_after_delete.status_code == 404
    assert delete_again.status_code == 404
