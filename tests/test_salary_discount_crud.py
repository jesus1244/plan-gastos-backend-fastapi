from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.database.connection import SessionLocal
from app.infrastructure.database.models import Budget, SalaryDiscount, User
from app.infrastructure.firebase_auth import get_db
from app.main import app


def _clear_user_data(firebase_uid: str) -> None:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one_or_none()
        if user is None:
            return
        for budget in list(user.budgets):
            for discount in list(budget.salary_discounts):
                session.delete(discount)
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


def test_discount_list_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get('/api/budgets/123/discounts')
    assert response.status_code == 401


def test_create_discount_for_owned_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'discount-user-1'
    _create_user(firebase_uid, 'discount1@example.com', 'Discount User One')
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-01', 'Budget One')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'discount1@example.com', 'name': 'Discount User One'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.post(
            f'/api/budgets/{budget_id}/discounts',
            json={'name': 'Salud', 'percentage': 4.0},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload['name'] == 'Salud'
    assert payload['enabled'] is True
    assert Decimal(str(payload['percentage'])) == Decimal('4.00')


def test_create_discount_in_other_users_budget_returns_404(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'discount-owner'
    attacker_uid = 'discount-attacker'
    _create_user(owner_uid, 'owner@example.com', 'Owner User')
    _create_user(attacker_uid, 'attacker@example.com', 'Attacker User')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget_id = _create_budget(str(owner.id), '2026-02', 'Other User Budget')

    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attacker@example.com', 'name': 'Attacker User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.post(
            f'/api/budgets/{budget_id}/discounts',
            json={'name': 'Salud', 'percentage': 5},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 404


def test_list_discounts_returns_only_current_budget(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'discount-list-user'
    _create_user(firebase_uid, 'list@example.com', 'List User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-03', 'List Budget')
        session.add_all(
            [
                SalaryDiscount(budget_id=budget_id, name='Salud', percentage=Decimal('4.00'), enabled=True),
                SalaryDiscount(budget_id=budget_id, name='AFP', percentage=Decimal('7.50'), enabled=False),
            ]
        )
        session.commit()

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'list@example.com', 'name': 'List User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/discounts', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert {item['name'] for item in payload} == {'Salud', 'AFP'}


def test_get_discount_for_other_budget_returns_404(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    owner_uid = 'discount-get-owner'
    attacker_uid = 'discount-get-attacker'
    _create_user(owner_uid, 'owner2@example.com', 'Owner Two')
    _create_user(attacker_uid, 'attacker2@example.com', 'Attacker Two')

    with SessionLocal() as session:
        owner = session.execute(select(User).where(User.firebase_uid == owner_uid)).scalar_one()
        budget_id = _create_budget(str(owner.id), '2026-04', 'Get Budget')
        discount = SalaryDiscount(budget_id=budget_id, name='Salud', percentage=Decimal('4.00'), enabled=True)
        session.add(discount)
        session.commit()
        session.refresh(discount)
        discount_id = str(discount.id)

    def fake_verify(token: str):
        return {'uid': attacker_uid, 'email': 'attacker2@example.com', 'name': 'Attacker Two'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.get(f'/api/budgets/{budget_id}/discounts/{discount_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 404


def test_patch_discount_updates_owned_fields(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'discount-patch-user'
    _create_user(firebase_uid, 'patchdiscount@example.com', 'Patch User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-05', 'Patch Budget')
        discount = SalaryDiscount(budget_id=budget_id, name='Salud', percentage=Decimal('4.00'), enabled=True)
        session.add(discount)
        session.commit()
        session.refresh(discount)
        discount_id = str(discount.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'patchdiscount@example.com', 'name': 'Patch User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/budgets/{budget_id}/discounts/{discount_id}',
            json={'name': 'Salud Plus', 'percentage': 6.5, 'enabled': False},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['name'] == 'Salud Plus'
    assert Decimal(str(payload['percentage'])) == Decimal('6.50')
    assert payload['enabled'] is False


def test_patch_discount_rejects_invalid_percentage(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'discount-invalid-user'
    _create_user(firebase_uid, 'invaliddiscount@example.com', 'Invalid Discount User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-06', 'Invalid Budget')
        discount = SalaryDiscount(budget_id=budget_id, name='Salud', percentage=Decimal('4.00'), enabled=True)
        session.add(discount)
        session.commit()
        session.refresh(discount)
        discount_id = str(discount.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'invaliddiscount@example.com', 'name': 'Invalid Discount User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.patch(
            f'/api/budgets/{budget_id}/discounts/{discount_id}',
            json={'percentage': 250},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert response.status_code == 422


def test_delete_discount_owned_only(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'discount-delete-user'
    _create_user(firebase_uid, 'delete@example.com', 'Delete User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-07', 'Delete Budget')
        discount = SalaryDiscount(budget_id=budget_id, name='Salud', percentage=Decimal('4.00'), enabled=True)
        session.add(discount)
        session.commit()
        session.refresh(discount)
        discount_id = str(discount.id)

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'delete@example.com', 'name': 'Delete User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        response = client.delete(f'/api/budgets/{budget_id}/discounts/{discount_id}', headers={'Authorization': 'Bearer valid-token'})

    assert response.status_code == 204

    with SessionLocal() as session:
        remaining = session.execute(select(SalaryDiscount).where(SalaryDiscount.id == discount_id)).scalar_one_or_none()
        assert remaining is None


def test_discount_validations_fail_for_invalid_payload(monkeypatch) -> None:
    from app.infrastructure import firebase_auth

    firebase_uid = 'discount-validation-user'
    _create_user(firebase_uid, 'validationdiscount@example.com', 'Validation User')

    with SessionLocal() as session:
        user = session.execute(select(User).where(User.firebase_uid == firebase_uid)).scalar_one()
        budget_id = _create_budget(str(user.id), '2026-08', 'Validation Budget')

    def fake_verify(token: str):
        return {'uid': firebase_uid, 'email': 'validationdiscount@example.com', 'name': 'Validation User'}

    monkeypatch.setattr(firebase_auth, 'verify_firebase_token', fake_verify)

    with TestClient(app) as client:
        empty_name = client.post(
            f'/api/budgets/{budget_id}/discounts',
            json={'name': '   ', 'percentage': 4},
            headers={'Authorization': 'Bearer valid-token'},
        )
        negative_percentage = client.post(
            f'/api/budgets/{budget_id}/discounts',
            json={'name': 'Salud', 'percentage': -1},
            headers={'Authorization': 'Bearer valid-token'},
        )
        too_large_percentage = client.post(
            f'/api/budgets/{budget_id}/discounts',
            json={'name': 'Salud', 'percentage': 100.01},
            headers={'Authorization': 'Bearer valid-token'},
        )

    assert empty_name.status_code == 422
    assert negative_percentage.status_code == 422
    assert too_large_percentage.status_code == 422
