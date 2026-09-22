from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.budgets import router as budgets_router
from app.api.routes.expenses import router as expenses_router
from app.api.routes.incomes import router as incomes_router
from app.api.routes.overtimes import router as overtime_router
from app.api.routes.salary_discounts import router as salary_discounts_router
from app.infrastructure.database.config import settings
from app.infrastructure.database.models.user import User
from app.infrastructure.firebase_auth import get_current_user

app = FastAPI(title="Plan Gastos API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(budgets_router)
app.include_router(incomes_router)
app.include_router(expenses_router)
app.include_router(overtime_router)
app.include_router(salary_discounts_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get('/api/me')
def get_authenticated_user(current_user: User = Depends(get_current_user)) -> dict[str, str | None]:
    return {
        'id': str(current_user.id),
        'firebase_uid': current_user.firebase_uid,
        'email': current_user.email,
        'display_name': current_user.display_name,
    }
