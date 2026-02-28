# Prism

Portable financial reputation platform. Upload financial documents (bank statements, rent receipts, utility bills, pay stubs), extract transactions with AI, build a trust score, and generate cryptographically signed credentials you can share with landlords, banks, or employers.

Built for cross-border scenarios where traditional credit scores don't transfer.

## Architecture

```
Frontend (Next.js)        Backend (FastAPI)         Database (PostgreSQL)
port 3000                 port 5555                 port 5432
  |                         |                         |
  |--- /api/* proxied ----->|--- SQLAlchemy async --->|
  |                         |
  |                         |--- IBM watsonx.ai (OCR + LLM)
  |                         |--- IBM Cloud Object Storage
  |                         |--- IBM watsonx Orchestrate
```

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS. Proxies `/api/*` requests to the backend.
- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Alembic migrations, JWT auth, RSA credential signing.
- **Database**: PostgreSQL 16 via Docker.
- **AI**: IBM watsonx.ai Granite LLM for document classification and transaction extraction. Optional IBM watsonx Orchestrate integration for multi-document analysis.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker (for PostgreSQL)
- IBM watsonx.ai API key (for document processing features)

## Quick Start

### 1. Start the database

```bash
docker compose up -d
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run database migrations:

```bash
alembic upgrade head
```

Start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 5555 --reload
```

### 3. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

The app is now running at **http://localhost:3000**. API docs are at **http://localhost:5555/docs**.

## Environment Variables

Create `backend/.env` (all prefixed with `TB_`):

```env
# Database (defaults work with docker-compose)
TB_DATABASE_URL=postgresql+asyncpg://trustbridge:trustbridge_dev@localhost:5432/trustbridge
TB_DATABASE_URL_SYNC=postgresql://trustbridge:trustbridge_dev@localhost:5432/trustbridge

# Auth
TB_JWT_SECRET=change-me-in-production

# IBM watsonx.ai (required for document processing)
TB_WATSONX_API_KEY=
TB_WATSONX_PROJECT_ID=
TB_WATSONX_URL=https://us-south.ml.cloud.ibm.com

# IBM Cloud Object Storage (required for document upload)
TB_COS_API_KEY=
TB_COS_INSTANCE_ID=
TB_COS_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud
TB_COS_BUCKET=trustbridge-documents

# IBM watsonx Orchestrate (optional, for financial agent)
TB_WXO_MCSP_APIKEY=
TB_WXO_INSTANCE_URL=
TB_WXO_AGENT_ID=

# Frontend URL (for credential share links)
TB_FRONTEND_URL=http://localhost:3000
```

RSA keys for credential signing are auto-generated on first use and stored in `backend/keys/`.

## Demo Data

Seed sample documents and transactions for a user:

```bash
cd backend
source venv/bin/activate

# First, sign up via the UI and get your user ID from the database
python seed_demo.py <user_id>
```

This creates 3 documents (bank statement, rent receipts, utility bills) with realistic transactions and auto-generates claims and a trust score.

To generate sample PDF files for manual upload testing:

```bash
pip install fpdf2
python generate_samples.py
# Outputs to ./sample-documents/
```

## Features

### Document Processing
Upload PDF, PNG, JPEG, or TIFF files (max 20 MB). Documents go through: upload to COS, OCR via watsonx.ai, classification by Granite LLM (bank statement / rent receipt / utility bill / pay stub), and structured transaction extraction.

### Trust Score
Weighted score from 0 to 100 based on verified transactions:

| Category | Weight | What it measures |
|---|---|---|
| Rent history | 30% | On-time rent payment rate |
| Income stability | 30% | Regular deposit frequency |
| Utility payments | 20% | On-time utility payment rate |
| Bank health | 20% | Net cash flow analysis |

### Verifiable Credentials
Select claims to include, set an expiry (24 hours to 30 days), and generate a shareable link. Credentials are signed with RS256 (RSA) and can be verified by anyone via the public `/verify/<token>` page without needing an account.

### Financial Agent
Multi-file upload interface with language and currency selection. Sends documents to IBM watsonx Orchestrate for structured financial analysis with income detection, loan identification, and obligation mapping.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Create account |
| `POST` | `/auth/login` | Login, returns JWT |
| `GET` | `/auth/me` | Current user profile |
| `POST` | `/documents/upload` | Upload a document |
| `GET` | `/documents/` | List documents |
| `GET` | `/documents/{id}` | Document detail + transactions |
| `GET` | `/documents/{id}/status` | Processing status |
| `GET` | `/reputation/profile` | Trust score + claims + breakdown |
| `GET` | `/reputation/claims` | List claims |
| `POST` | `/reputation/recalculate` | Regenerate claims from transactions |
| `POST` | `/credentials/generate` | Create signed credential |
| `GET` | `/credentials/` | List credentials |
| `DELETE` | `/credentials/{id}` | Revoke credential |
| `GET` | `/credentials/verify/{token}` | Public verification (no auth) |
| `POST` | `/agent/upload` | Upload files for agent analysis |
| `POST` | `/agent/analyze` | Run financial analysis |

## Project Structure

```
trustbridge/
├── backend/
│   ├── app/
│   │   ├── auth/            # Signup, login, JWT
│   │   ├── documents/       # Upload, processing pipeline
│   │   ├── credentials/     # RSA signing, share links
│   │   ├── reputation/      # Trust score algorithm, claims
│   │   ├── agent/           # watsonx Orchestrate integration
│   │   ├── watson/          # watsonx.ai + COS helpers
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   └── database.py      # Async engine + session
│   ├── alembic/             # Database migrations
│   ├── seed_demo.py         # Demo data seeder
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages (dashboard, documents, credentials, etc.)
│   │   ├── components/      # AppLayout, Sidebar, TrustScoreGauge
│   │   ├── contexts/        # AuthContext
│   │   └── lib/             # API client
│   ├── Dockerfile
│   └── next.config.mjs      # /api proxy to backend
├── docker-compose.yml        # PostgreSQL
└── generate_samples.py       # Sample PDF generator
```
