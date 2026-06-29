# InfoBridge

InfoBridge is a secure inter-institution exchange platform for official cases, messages, files, receipts, workflows, audit logs, and security events.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL
- Frontend: React, Vite, TypeScript
- File storage target: S3 compatible storage such as MinIO

## Quick Start

1. Copy environment variables:

```bash
cp .env.example .env
```

2. Start infrastructure:

```bash
docker compose up -d postgres minio
```

Or start the full local stack:

```bash
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health
- API docs: http://localhost:8000/docs

3. Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

4. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Railway Deployment

Create one Railway project with three services:

1. PostgreSQL database service
2. Backend service from this repository with root directory `backend`
3. Frontend service from this repository with root directory `frontend`

### Backend Variables

Set these variables on the backend service:

```bash
DATABASE_URL=${{ Postgres.DATABASE_URL }}
SECRET_KEY=replace-with-a-long-random-secret
API_CORS_ORIGINS=https://your-frontend-domain.up.railway.app
ACCESS_TOKEN_EXPIRE_MINUTES=15
```

The backend listens on Railway's injected `PORT` and exposes `/health`.

### Frontend Variables

Set this variable on the frontend service:

```bash
VITE_API_URL=https://your-backend-domain.up.railway.app/api/v1
```

The frontend is built with Vite and served by Caddy. Caddy listens on Railway's injected `PORT` and supports SPA fallback routing.

### Deployment Order

1. Deploy PostgreSQL.
2. Deploy the backend and generate a public domain.
3. Put the backend public domain into the frontend `VITE_API_URL`.
4. Deploy the frontend and generate a public domain.
5. Put the frontend public domain into the backend `API_CORS_ORIGINS`.
6. Redeploy the backend.

## MVP Scope

- Institutions and users
- Exchange cases with classification and statuses
- Messages and attachments metadata
- Receipts
- Workflows and workflow actions
- Audit logs for business traceability
- Security events for suspicious activity detection
