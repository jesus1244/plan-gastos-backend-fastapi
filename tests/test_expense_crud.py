from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, Expense, User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user_data(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is None:
            return
        for budget in list(user.budgets):
            for expense in list(budget.expenses):
                session.delete(expense)
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


def test_expenses_require_authentication() -> None:
    with TestClient(app) as client:
        response = client.get('/api/budgets/123/expenses')
    assert response.status_code == 401


def test_invalid_token_is_rejected(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    def fake_verify(token: str):
        raise ValueError('bad token')

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get('/api/budgets/123/expenses', headers={'Authorization': 'Bearer bad-token'})

    assert response.status_code == 401


def test_create_expense_for_owned_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'expense-user-1'
    _create_user(firebase_uid, 'expense1@example.com', 'Expense User One')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-01', 'Budget One')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'expense1@example.com', 'name': 'Expense User One'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.post(
            f'/api/budgets/{budget_id}/expenses',
            json={'name': 'Alquiler', 'amount': 800000.25, 'type': 'fixed'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload['name'] == 'Alquiler'
    assert Decimal(str(payload['amount'])) == Decimal('800000.25')
    assert payload['type'] == 'fixed'
    assert payload['budget_id'] == budget_id


def test_create_expense_validates_name_amount_and_type(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'expense-validation-user'
    _create_user(firebase_uid, 'validationexpense@example.com', 'Validation User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-02', 'Validation Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'validationexpense@example.com', 'name': 'Validation User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        empty_name = client.post(
            f'/api/budgets/{budget_id}/expenses',
            json={'name': '   ', 'amount': 1000, 'type': 'fixed'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        negative_amount = client.post(
            f'/api/budgets/{budget_id}/expenses',
            json={'name': 'Alquiler', 'amount': -1, 'type': 'fixed'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        missing_amount = client.post(
            f'/api/budgets/{budget_id}/expenses',
            json={'name': 'Alquiler', 'type': 'fixed'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        invalid_type = client.post(
            f'/api/budgets/{budget_id}/expenses',
            json={'name': 'Alquiler', 'amount': 1000, 'type': 'invalid'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        budget_override = client.post(
            f'/api/budgets/{budget_id}/expenses',
            json={'name': 'Alquiler', 'amount': 1000, 'type': 'fixed', 'budget_id': 'another-budget'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert empty_name.status_code == 422
    assert negative_amount.status_code == 422
    assert missing_amount.status_code == 422
    assert invalid_type.status_code == 422
    assert budget_override.status_code == 422


def test_list_expenses_returns_owned_budget_only(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'expense-list-user'
    _create_user(firebase_uid, 'listexpense@example.com', 'List User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-03', 'List Budget')
        session.add_all(
            [
                Expense(budget_id=budget_id, name='Alquiler', amount=Decimal('800000.00'), type='fixed'),
                Expense(budget_id=budget_id, name='Supermercado', amount=Decimal('250000.00'), type='other'),
            ]
        )
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'listexpense@example.com', 'name': 'List User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/expenses', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert {item['name'] for item in payload} == {'Alquiler', 'Supermercado'}


def test_get_expense_for_other_user_returns_404(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'expense-owner'
    attacker_uid = 'expense-attacker'
    _create_user(owner_uid, 'ownerexpense@example.com', 'Owner Expense')
    _create_user(attacker_uid, 'attackerexpense@example.com', 'Attacker Expense')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget_id = _create_budget(str(owner.id), '2026-04', 'Owned Budget')
        expense = Expense(budget_id=budget_id, name='Alquiler', amount=Decimal('600000.00'), type='fixed')
        session.add(expense)
        session.commit()
        session.refresh(expense)
        expense_id = str(expense.id)

    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attackerexpense@example.com', 'name': 'Attacker Expense'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/expenses/{expense_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 404


def test_update_expense_changes_allowed_fields_only(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'expense-update-user'
    _create_user(firebase_uid, 'updateexpense@example.com', 'Update User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-05', 'Update Budget')
        expense = Expense(budget_id=budget_id, name='Alquiler', amount=Decimal('600000.00'), type='fixed')
        session.add(expense)
        session.commit()
        session.refresh(expense)
        expense_id = str(expense.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'updateexpense@example.com', 'name': 'Update User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/budgets/{budget_id}/expenses/{expense_id}',
            json={'name': 'Alquiler Ajustado', 'amount': 720000.50, 'type': 'other'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        blocked_budget_change = client.patch(
            f'/api/budgets/{budget_id}/expenses/{expense_id}',
            json={'budget_id': 'other-budget'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 200
    assert response.json()['name'] == 'Alquiler Ajustado'
    assert Decimal(str(response.json()['amount'])) == Decimal('720000.50')
    assert response.json()['type'] == 'other'
    assert blocked_budget_change.status_code == 422


def test_delete_expense_requires_ownership(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'expense-delete-owner'
    attacker_uid = 'expense-delete-attacker'
    _create_user(owner_uid, 'ownerdeleteexpense@example.com', 'Owner Delete')
    _create_user(attacker_uid, 'attackerdeleteexpense@example.com', 'Attacker Delete')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget_id = _create_budget(str(owner.id), '2026-06', 'Delete Budget')
        expense = Expense(budget_id=budget_id, name='Alquiler', amount=Decimal('650000.00'), type='fixed')
        session.add(expense)
        session.commit()
        session.refresh(expense)
        expense_id = str(expense.id)

    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attackerdeleteexpense@example.com', 'name': 'Attacker Delete'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.delete(f'/api/budgets/{budget_id}/expenses/{expense_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 404

    with SessionLocal() as session:
        remaining = session.execute(select(Expense).where(Expense.id == expense_id)).scalar_one_or_none()
        assert remaining is not None


def test_expense_ownership_rejects_other_budget_and_wrong_expense_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    user_a_uid = 'expense-user-a'
    user_b_uid = 'expense-user-b'
    _create_user(user_a_uid, 'aexpense@example.com', 'User A')
    _create_user(user_b_uid, 'bexpense@example.com', 'User B')

    with SessionLocal() as session:
        user_a = session.execute(select(User).where(User.firebase_uid == user_a_uid)).scalar_one()
        user_b = session.execute(select(User).where(User.firebase_uid == user_b_uid)).scalar_one()
        budget_a_id = _create_budget(str(user_a.id), '2026-07', 'Budget A')
        budget_b_id = _create_budget(str(user_b.id), '2026-08', 'Budget B')

        expense_a = Expense(budget_id=budget_a_id, name='Gasto A', amount=Decimal('900000.00'), type='fixed')
        expense_b = Expense(budget_id=budget_b_id, name='Gasto B', amount=Decimal('1100000.00'), type='other')
        session.add_all([expense_a, expense_b])
        session.commit()
        session.refresh(expense_a)
        session.refresh(expense_b)
        expense_a_id = str(expense_a.id)
        expense_b_id = str(expense_b.id)

    def fake_verify(token: str):
        return {'uid': user_a_uid, 'email': 'aexpense@example.com', 'name': 'User A'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        list_response = client.get(f'/api/budgets/{budget_b_id}/expenses', headers={'Authorization': 'Bearer valid-token'})
        create_response = client.post(
            f'/api/budgets/{budget_b_id}/expenses',
            json={'name': 'Intruso', 'amount': 1234.56, 'type': 'fixed'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        get_response = client.get(f'/api/budgets/{budget_b_id}/expenses/{expense_b_id}', headers={'Authorization': 'Bearer valid-token'})
        patch_response = client.patch(
            f'/api/budgets/{budget_b_id}/expenses/{expense_b_id}',
            json={'name': 'Hacked'},
            headers={'Authorization': 'Bearer valid-token'},
        )
        delete_response = client.delete(f'/api/budgets/{budget_b_id}/expenses/{expense_b_id}', headers={'Authorization': 'Bearer valid-token'})
        cross_budget_response = client.patch(
            f'/api/budgets/{budget_a_id}/expenses/{expense_b_id}',
            json={'name': 'Wrong budget'},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert list_response.status_code == 404
    assert create_response.status_code == 404
    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
    assert cross_budget_response.status_code == 404


def test_expense_delete_removes_record(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'expense-delete-user'
    _create_user(firebase_uid, 'deleteexpense@example.com', 'Delete Expense User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-09', 'Delete Expense Budget')
        expense = Expense(budget_id=budget_id, name='Gasto', amount=Decimal('500000.00'), type='other')
        session.add(expense)
        session.commit()
        session.refresh(expense)
        expense_id = str(expense.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'deleteexpense@example.com', 'name': 'Delete Expense User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        delete_response = client.delete(f'/api/budgets/{budget_id}/expenses/{expense_id}', headers={'Authorization': 'Bearer valid-token'})
        get_after_delete = client.get(f'/api/budgets/{budget_id}/expenses/{expense_id}', headers={'Authorization': 'Bearer valid-token'})

    assert delete_response.status_code == 204
    assert get_after_delete.status_code == 404
