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

## Tests

The integration suite creates and removes an isolated PostgreSQL schema. Point it to a dedicated test database:

```bash
cd backend
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+psycopg://infobridge:infobridge_dev_password@localhost:5432/infobridge_test \
  python -m unittest discover -s tests -v
```

Tests that require PostgreSQL are skipped when `TEST_DATABASE_URL` is absent.

## Demo account

After applying migrations, initialize or refresh the local demonstration data with:

```bash
cd backend
python scripts/seed_demo.py
```

The system administrator is `admin@infobridge.bi` with the development-only password
`ChangeMeStrong123!`. Re-running the seed migrates the former `admin@infobridge.local` account, unlocks it, and resets
its demo password. Never run this seed against a production database.

## Automatic reminders

The backend scans open cases automatically at startup and then every
`LIFECYCLE_SCAN_INTERVAL_SECONDS` seconds. `DUE_SOON_HOURS` controls the upcoming-deadline window, while
`DUE_ALERTS_ENABLED` and `LIFECYCLE_WORKER_ENABLED` can disable reminders or the complete lifecycle worker.
Daily reminders use a database deduplication key, and a PostgreSQL advisory lock prevents concurrent backend
instances from running the same lifecycle scan simultaneously.

## Controlled document purge

Archiving a document is a reversible logical deletion while its case remains inside the retention period. Physical
deletion becomes eligible only when the parent case is archived and `retention_until` has passed. System admins can
inspect `GET /api/v1/documents/purge-preview` and explicitly invoke `POST /api/v1/documents/purge-expired` with the
confirmation value `PURGE_EXPIRED_DOCUMENTS`. Set `DOCUMENT_PURGE_ENABLED=true` only after validating the retention
policy to include this purge in automatic lifecycle scans. Purged metadata and checksums remain available for audit.

## Security and retention settings

System administrators can update the effective security, retention, and lifecycle values from the administration
screen. Institution administrators have read-only access. Values are validated, persisted in `platform_settings`,
and recorded in the audit log; environment variables remain the defaults until a value is saved. Apply migration
`0014_platform_settings` before using the screen. MFA is explicitly shown as unavailable until it is implemented.

## Configurable reference data

Migration `0015_reference_data` adds controlled overrides for institution types, case priorities, information
classifications, and attachment purposes. System administrators can change labels, descriptions, display order, and
availability from the administration screen. Disabled values remain visible on historical records but are rejected
for new records. The stable codes and mandatory defaults remain protected because they are used by PostgreSQL enums,
permission checks, and workflow rules.

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
REFRESH_TOKEN_EXPIRE_DAYS=7
```

The backend listens on Railway's injected `PORT` and exposes `/health`.

### Frontend Variables

Set this variable on the frontend service:

```bash
VITE_API_URL=https://your-backend-domain.up.railway.app/api/v1
```

The frontend is built with Vite and served by Caddy. Caddy listens on Railway's injected `PORT` and supports SPA fallback routing.

## Append-only audit log

Migration `0013_audit_log_append_only` installs PostgreSQL `ALWAYS` triggers that reject `UPDATE`, `DELETE`, and
`TRUNCATE` operations on `audit_logs`. SQLAlchemy also rejects ORM update and delete operations before they reach the
database. In production, use separate migration and runtime database roles; grant the runtime role only `SELECT` and
`INSERT` on `audit_logs`, and never run the API with a PostgreSQL superuser or a role allowed to bypass triggers.

Append-only enforcement protects against application mistakes and ordinary SQL mutations. Database superusers still
control the database, so regulated deployments should additionally ship PostgreSQL logs and audit exports to an
independent immutable archive.

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

## Document storage and encryption keys

Set `DOCUMENT_STORAGE_BACKEND=s3` to use AWS S3 or a compatible service such as MinIO. Configure
`S3_BUCKET`, credentials, region, and optionally `S3_ENDPOINT_URL` for compatible services. Each attachment records
its own backend; existing local files remain readable only while their original disk or persistent volume is mounted.

Encryption keys are versioned through a JSON keyring. Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then configure, for example:

```env
DOCUMENT_ENCRYPTION_KEYS={"2026-v1":"generated-key"}
DOCUMENT_ACTIVE_ENCRYPTION_KEY_ID=2026-v1
```

To rotate keys, add a new entry and change the active ID. Keep old entries available until every document using
them has passed its retention period. Never commit production keys or S3 credentials.

### AWS KMS envelope encryption

For production, set `DOCUMENT_ENCRYPTION_PROVIDER=aws_kms` and `AWS_KMS_KEY_ID` to a symmetric KMS key ID, ARN, or
alias. `AWS_KMS_REGION` defaults to `us-east-1`. The AWS SDK default credential chain is used unless the optional
`AWS_KMS_ACCESS_KEY_ID`, `AWS_KMS_SECRET_ACCESS_KEY`, and `AWS_KMS_SESSION_TOKEN` variables are provided. Grant the
backend only `kms:GenerateDataKey` and `kms:Decrypt` on that key.

Each new document receives a unique AES-256 data key. InfoBridge stores only the KMS-encrypted data key, the nonce,
and the encrypted document. Existing Fernet documents remain readable; switching providers does not require an
immediate data migration.

## Audit exports

Authorized system admins, institution admins, and auditors can export the audit trail through
`GET /api/v1/audit-logs/export?format=csv` or `format=pdf`. Optional `action`, `entity_type`, `date_from`, `date_to`,
and `limit` parameters restrict the export. Non-system users remain scoped to their institution, and every export is
itself recorded as an `AUDIT_EXPORTED` event.

## M2M authentication

Migration `0016_m2m_token_control` adds immediate token invalidation for API-client suspension, scope changes, and
secret rotation. Administrators manage clients from **Administration → Interopérabilité**. Institution
administrators can manage only clients attached to their institution; only system administrators can create a global
client.

Available scopes are deliberately limited to implemented operations:

- `cases:read`: list and inspect cases through `/api/v1/external/cases`.
- `documents:read`: list and download case attachments through `/api/v1/external/cases/{case_id}/attachments`.

Exchange a client ID and its one-time secret at `POST /api/v1/integrations/token`, then send the returned bearer
token to external endpoints. Every request is checked against both the signed token and the current database state,
including token version, active scopes, client status, and institution status. Failed client authentication is
recorded as a security event.
