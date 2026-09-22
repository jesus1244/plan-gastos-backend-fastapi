# Plan Gastos API

Backend FastAPI para la aplicación Plan Gastos.

## Requisitos


## Configuración local

Copia el ejemplo de entorno:

```bash
cp .env.example .env
```

Ajusta los valores. En Firebase Admin SDK es necesario definir:

```env
FIREBASE_PROJECT_ID=example-project-id
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@example.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nexample-private-key\n-----END PRIVATE KEY-----\n"
```

No se debe commitear un `.env` real ni credenciales de Firebase reales.

## Instalar dependencias

```bash
python -m venv .venv
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Luego:

```bash
pip install -e ".[dev]"
```

## Ejecutar la API localmente

```bash
uvicorn app.main:app --reload
```

La API estará disponible en:


## Autenticación Firebase

El backend valida Firebase ID Tokens mediante el header:

```http
Authorization: Bearer <ID_TOKEN>
```

### GET /api/me


El usuario se crea o sincroniza en la tabla `users` usando el `firebase_uid`.

## Budgets por usuario autenticado

Los endpoints de budgets están aislados por usuario. Cada budget pertenece al usuario autenticado y se valida el `user_id` del token sobre PostgreSQL.

### Endpoints

```http
GET /api/budgets
GET /api/budgets/{budget_id}
POST /api/budgets
PATCH /api/budgets/{budget_id}
DELETE /api/budgets/{budget_id}
```


## Salary discounts por budget autenticado

Los descuentos salariales se gestionan bajo ownership del budget. La validación se hace chequeando que el `budget.user_id` corresponda al usuario autenticado antes de crear, listar, consultar, actualizar o borrar descuentos.

### Endpoints

```http
GET /api/budgets/{budget_id}/discounts
POST /api/budgets/{budget_id}/discounts
GET /api/budgets/{budget_id}/discounts/{discount_id}
PATCH /api/budgets/{budget_id}/discounts/{discount_id}
DELETE /api/budgets/{budget_id}/discounts/{discount_id}
```


## Ejecutar con Docker Compose

```bash
docker compose up --build
```

Esto levantará PostgreSQL y la API, y antes de arrancar FastAPI ejecutará:

```bash
alembic upgrade head
```

## Ejecutar migraciones manualmente

```bash
alembic upgrade head
```

## Ejecutar tests

```bash
pytest
```

## Detener entorno

```bash
docker compose down
```
