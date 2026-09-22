from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user_data(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is None:
            return
        for budget in list(user.budgets):
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


def _override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides.clear()
app.dependency_overrides[get_db] = _override_get_db


def test_budgets_require_authentication() -> None:
    with TestClient(app) as client:
        response = client.get('/api/budgets')
    assert response.status_code == 401


def test_list_budgets_returns_only_current_user(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    user_one_uid = 'budget-user-1'
    user_two_uid = 'budget-user-2'
    _create_user(user_one_uid, 'one@example.com', 'User One')
    _create_user(user_two_uid, 'two@example.com', 'User Two')

    with SessionLocal() as session:
        user_one = session.execute(select(User).where(User.firebase_uid == user_one_uid)).scalar_one()
        user_two = session.execute(select(User).where(User.firebase_uid == user_two_uid)).scalar_one()
        session.add_all(
            [
                Budget(user_id=user_one.id, name='Budget One', month_key='2026-09', base_salary=Decimal('3000000')),
                Budget(user_id=user_two.id, name='Budget Two', month_key='2026-09', base_salary=Decimal('4000000')),
            ]
        )
        session.commit()

    def fake_verify(token: str):
        return {'uid': user_one_uid, 'email': 'one@example.com', 'name': 'User One'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/budgets', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]['name'] == 'Budget One'


def test_create_budget_assigns_current_user_and_rejects_duplicate_month(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'budget-creator'
    _create_user(firebase_uid, 'creator@example.com', 'Creator User')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'creator@example.com', 'name': 'Creator User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    payload = {
        'name': 'Septiembre 2026',
        'month_key': '2026-09',
        'base_salary': 3000000,
    }

    with TestClient(app) as client:
        first = client.post('/api/budgets', json=payload, headers={'Authorization': 'Bearer valid-token'})
        second = client.post('/api/budgets', json=payload, headers={'Authorization': 'Bearer valid-token'})

    assert first.status_code == 201
    assert second.status_code == 409

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budgets = session.execute(select(Budget).where(Budget.user_id == user.id)).scalars().all()
        assert len(budgets) == 1
        assert budgets[0].name == 'Septiembre 2026'
        assert str(budgets[0].user_id) == str(user.id)


def test_get_budget_for_other_user_returns_404(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'budget-owner'
    attacker_uid = 'budget-attacker'
    _create_user(owner_uid, 'owner@example.com', 'Owner')
    _create_user(attacker_uid, 'attacker@example.com', 'Attacker')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget = Budget(user_id=owner.id, name='Owned Budget', month_key='2026-11', base_salary=Decimal('2500000'))
        session.add(budget)
        session.commit()
        session.refresh(budget)
        budget_id = str(budget.id)
    
    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attacker@example.com', 'name': 'Attacker'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 404


def test_patch_budget_updates_only_owned_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'patch-user'
    _create_user(firebase_uid, 'patch@example.com', 'Patch User')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'patch@example.com', 'name': 'Patch User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget = Budget(user_id=user.id, name='Old Budget', month_key='2026-10', base_salary=Decimal('2000000'))
        session.add(budget)
        session.commit()
        session.refresh(budget)
        budget_id = str(budget.id)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/budgets/{budget_id}',
            json={'name': 'Updated Budget', 'base_salary': 2200000},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['name'] == 'Updated Budget'
    assert Decimal(payload['base_salary']) == Decimal('2200000.00')


def test_patch_budget_rejects_duplicate_month_key(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'duplicate-patch-user'
    _create_user(firebase_uid, 'duplicate@example.com', 'Duplicate User')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'duplicate@example.com', 'name': 'Duplicate User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        first = Budget(user_id=user.id, name='First Budget', month_key='2026-12', base_salary=Decimal('2100000'))
        second = Budget(user_id=user.id, name='Second Budget', month_key='2026-11', base_salary=Decimal('2200000'))
        session.add_all([first, second])
        session.commit()
        session.refresh(first)
        session.refresh(second)
        first_id = str(first.id)
        second_id = str(second.id)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/budgets/{first_id}',
            json={'month_key': '2026-11'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 409

    with SessionLocal() as session:
        budget = session.execute(select(Budget).where(Budget.id == first_id)).scalar_one()
        assert budget.month_key == '2026-12'


def test_delete_budget_owned_only(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'delete-user'
    _create_user(firebase_uid, 'delete@example.com', 'Delete User')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'delete@example.com', 'name': 'Delete User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget = Budget(user_id=user.id, name='Delete Me', month_key='2026-08', base_salary=Decimal('1700000'))
        session.add(budget)
        session.commit()
        session.refresh(budget)
        budget_id = str(budget.id)

    with TestClient(app) as client:
        response = client.delete(f'/api/budgets/{budget_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 204

    with SessionLocal() as session:
        count = session.execute(select(Budget).where(Budget.id == budget_id)).scalar_one_or_none()
        assert count is None


def test_budget_validations_fail_for_invalid_payload(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'validation-user'
    _create_user(firebase_uid, 'validation@example.com', 'Validation User')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'validation@example.com', 'name': 'Validation User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        empty_name = client.post(
            '/api/budgets',
            json={'name': '   ', 'month_key': '2026-09', 'base_salary': 3000000},
            headers={'Authorization': 'Bearer valid-token'},
        )
        invalid_month = client.post(
            '/api/budgets',
            json={'name': 'Budget', 'month_key': '2026/09', 'base_salary': 3000000},
            headers={'Authorization': 'Bearer valid-token'},
        )
        negative_salary = client.post(
            '/api/budgets',
            json={'name': 'Budget', 'month_key': '2026-09', 'base_salary': -10},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert empty_name.status_code == 422
    assert invalid_month.status_code == 422
    assert negative_salary.status_code == 422
