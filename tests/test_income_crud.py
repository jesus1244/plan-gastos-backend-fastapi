from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, Income, User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user_data(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is None:
            return
        for budget in list(user.budgets):
            for income in list(budget.incomes):
                session.delete(income)
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


def test_incomes_require_authentication() -> None:
    with TestClient(app) as client:
        response = client.get('/api/budgets/123/incomes')
    assert response.status_code == 401


def test_invalid_token_is_rejected(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    def fake_verify(token: str):
        raise ValueError('bad token')

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/budgets/123/incomes', headers={'Authorization': 'Bearer bad-token'})

    assert response.status_code == 401


def test_create_income_for_owned_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'income-user-1'
    _create_user(firebase_uid, 'income1@example.com', 'Income User One')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-01', 'Budget One')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'income1@example.com', 'name': 'Income User One'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.post(
            f'/api/budgets/{budget_id}/incomes',
            json={'name': 'Salario', 'amount': 1500000.50},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload['name'] == 'Salario'
    assert Decimal(str(payload['amount'])) == Decimal('1500000.50')
    assert payload['budget_id'] == budget_id


def test_create_income_validates_name_and_amount(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'income-validation-user'
    _create_user(firebase_uid, 'validationincome@example.com', 'Validation User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-02', 'Validation Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'validationincome@example.com', 'name': 'Validation User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        empty_name = client.post(
            f'/api/budgets/{budget_id}/incomes',
            json={'name': '   ', 'amount': 1000},
            headers={'Authorization': 'Bearer valid-token'},
        )
        spaces_only = client.post(
            f'/api/budgets/{budget_id}/incomes',
            json={'name': '   ', 'amount': 1000},
            headers={'Authorization': 'Bearer valid-token'},
        )
        negative_amount = client.post(
            f'/api/budgets/{budget_id}/incomes',
            json={'name': 'Salario', 'amount': -1},
            headers={'Authorization': 'Bearer valid-token'},
        )
        missing_amount = client.post(
            f'/api/budgets/{budget_id}/incomes',
            json={'name': 'Salario'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        invalid_budget_id = client.post(
            f'/api/budgets/{budget_id}/incomes',
            json={'name': 'Salario', 'amount': 1000, 'budget_id': 'different-id'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert empty_name.status_code == 422
    assert spaces_only.status_code == 422
    assert negative_amount.status_code == 422
    assert missing_amount.status_code == 422
    assert invalid_budget_id.status_code == 422


def test_list_incomes_returns_owned_budget_only(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'income-list-user'
    _create_user(firebase_uid, 'listincome@example.com', 'List User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-03', 'List Budget')
        session.add_all(
            [
                Income(budget_id=budget_id, name='Salario', amount=Decimal('1500000.00')),
                Income(budget_id=budget_id, name='Bono', amount=Decimal('500000.00')),
            ]
        )
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'listincome@example.com', 'name': 'List User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/incomes', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert {item['name'] for item in payload} == {'Salario', 'Bono'}


def test_get_income_for_other_user_returns_404(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'income-owner'
    attacker_uid = 'income-attacker'
    _create_user(owner_uid, 'ownerincome@example.com', 'Owner Income')
    _create_user(attacker_uid, 'attackerincome@example.com', 'Attacker Income')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget_id = _create_budget(str(owner.id), '2026-04', 'Owned Budget')
        income = Income(budget_id=budget_id, name='Salario', amount=Decimal('2000000.00'))
        session.add(income)
        session.commit()
        session.refresh(income)
        income_id = str(income.id)

    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attackerincome@example.com', 'name': 'Attacker Income'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/incomes/{income_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 404


def test_update_income_changes_allowed_fields_only(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'income-update-user'
    _create_user(firebase_uid, 'updateincome@example.com', 'Update User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-05', 'Update Budget')
        income = Income(budget_id=budget_id, name='Salario', amount=Decimal('1000000.00'))
        session.add(income)
        session.commit()
        session.refresh(income)
        income_id = str(income.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'updateincome@example.com', 'name': 'Update User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/budgets/{budget_id}/incomes/{income_id}',
            json={'name': 'Sueldo Ajustado', 'amount': 1300000.75},
            headers={'Authorization': 'Bearer valid-token'},
        )
        blocked_budget_change = client.patch(
            f'/api/budgets/{budget_id}/incomes/{income_id}',
            json={'budget_id': 'other-budget'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 200
    assert response.json()['name'] == 'Sueldo Ajustado'
    assert Decimal(str(response.json()['amount'])) == Decimal('1300000.75')
    assert blocked_budget_change.status_code == 422


def test_delete_income_requires_ownership(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'income-delete-owner'
    attacker_uid = 'income-delete-attacker'
    _create_user(owner_uid, 'ownerdelete@example.com', 'Owner Delete')
    _create_user(attacker_uid, 'attackerdelete@example.com', 'Attacker Delete')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget_id = _create_budget(str(owner.id), '2026-06', 'Delete Budget')
        income = Income(budget_id=budget_id, name='Salario', amount=Decimal('1200000.00'))
        session.add(income)
        session.commit()
        session.refresh(income)
        income_id = str(income.id)

    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attackerdelete@example.com', 'name': 'Attacker Delete'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.delete(f'/api/budgets/{budget_id}/incomes/{income_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 404

    with SessionLocal() as session:
        remaining = session.execute(select(Income).where(Income.id == income_id)).scalar_one_or_none()
        assert remaining is not None


def test_income_ownership_rejects_other_budget_and_wrong_income_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    user_a_uid = 'income-user-a'
    user_b_uid = 'income-user-b'
    _create_user(user_a_uid, 'a@example.com', 'User A')
    _create_user(user_b_uid, 'b@example.com', 'User B')

    with SessionLocal() as session:
        user_a = session.execute(select(User).where(User.firebase_uid == user_a_uid)).scalar_one()
        user_b = session.execute(select(User).where(User.firebase_uid == user_b_uid)).scalar_one()
        budget_a_id = _create_budget(str(user_a.id), '2026-07', 'Budget A')
        budget_b_id = _create_budget(str(user_b.id), '2026-08', 'Budget B')

        income_a = Income(budget_id=budget_a_id, name='Ingreso A', amount=Decimal('900000.00'))
        income_b = Income(budget_id=budget_b_id, name='Ingreso B', amount=Decimal('1100000.00'))
        session.add_all([income_a, income_b])
        session.commit()
        session.refresh(income_a)
        session.refresh(income_b)
        income_a_id = str(income_a.id)
        income_b_id = str(income_b.id)

    def fake_verify(token: str):
        return {'uid': user_a_uid, 'email': 'a@example.com', 'name': 'User A'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        list_response = client.get(f'/api/budgets/{budget_b_id}/incomes', headers={'Authorization': 'Bearer valid-token'})
        create_response = client.post(
            f'/api/budgets/{budget_b_id}/incomes',
            json={'name': 'Intruso', 'amount': 1234.56},
            headers={'Authorization': 'Bearer valid-token'},
        )
        get_response = client.get(f'/api/budgets/{budget_b_id}/incomes/{income_b_id}', headers={'Authorization': 'Bearer valid-token'})
        patch_response = client.patch(
            f'/api/budgets/{budget_b_id}/incomes/{income_b_id}',
            json={'name': 'Hacked'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        delete_response = client.delete(f'/api/budgets/{budget_b_id}/incomes/{income_b_id}', headers={'Authorization': 'Bearer valid-token'})
        cross_budget_response = client.patch(
            f'/api/budgets/{budget_a_id}/incomes/{income_b_id}',
            json={'name': 'Wrong budget'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert list_response.status_code == 404
    assert create_response.status_code == 404
    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert cross_budget_response.status_code == 404


def test_income_delete_removes_record(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'income-delete-user'
    _create_user(firebase_uid, 'deleteincome@example.com', 'Delete Income User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-09', 'Delete Income Budget')
        income = Income(budget_id=budget_id, name='Ingreso', amount=Decimal('500000.00'))
        session.add(income)
        session.commit()
        session.refresh(income)
        income_id = str(income.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'deleteincome@example.com', 'name': 'Delete Income User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        delete_response = client.delete(f'/api/budgets/{budget_id}/incomes/{income_id}', headers={'Authorization': 'Bearer valid-token'})
        get_after_delete = client.get(f'/api/budgets/{budget_id}/incomes/{income_id}', headers={'Authorization': 'Bearer valid-token'})

    assert delete_response.status_code == 204
    assert get_after_delete.status_code == 404
