# Snorlax — Secure Cloud Storage

Light-themed, encrypted cloud storage with buckets & objects. Backend is FastAPI + PostgreSQL, files are XOR-encrypted per-bucket. Frontend is a single `index.html`.

## Prerequisites

- Python 3.10+
- PostgreSQL running and a database created (e.g. `snorlax`)

## 1. Setup

```bash
git clone https://github.com/Srinath-N-Gudi/Snorlax.git
cd "Snorlax"
```

Create env file from example:

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env`:

```
host=localhost
port=5432
dbname=snorlax
user=postgres
password=postgres
storage=storage
```

| var | meaning |
|---|---|
| `host`/`port`/`dbname`/`user`/`password` | Postgres connection |
| `storage` | folder where encrypted files are stored (created auto) |

## 2. Install Python packages

```bash
pip install fastapi uvicorn "psycopg[binary]" python-dotenv
```

## 3. Start Backend

From project root:

```bash
uvicorn backend.server:app --reload --port 5050
```

Backend → `http://localhost:5050`  
Health: tables are auto-created on first run.

## 4. Start Frontend

Frontend is static. Serve it on `http://localhost:5500` (CORS is whitelisted for this origin):

```bash
# Python (recommended)
python -m http.server 5500 --directory frontend

# or VS Code Live Server -> Open frontend/index.html with Live Server on port 5500
# or Node
npx serve frontend -l 5500
```

Open `http://localhost:5500` in browser. API base is `http://localhost:5050` (`frontend/index.html` → `const API`).

## Features

- Auth: register / login (cookie `session_id`, 24h)
- Buckets: create, list, rename, change encryption password (needs old password), delete
- Objects: upload (public/private), list, toggle public/private, rename, download, delete
- Settings: update username/password, delete account

## API Quick Reference

| Method | Path | Auth |
|---|---|---|
| POST | `/` | create user |
| POST | `/login` | login |
| PATCH/DELETE | `/` | update/delete user |
| POST | `/create-bucket` | create bucket |
| GET | `/buckets` | list buckets |
| PATCH/DELETE | `/buckets/{bucket_id}` | bucket settings |
| POST | `/buckets/{bucket_id}/create-object` | create object meta |
| GET | `/buckets/{bucket_id}` | list objects |
| PATCH/DELETE | `/buckets/{bucket_id}/{object_uuid}` | object settings (name, is_public) |
| PUT | `/buckets/{bucket_id}/{object_uuid}` | upload file bytes |
| GET | `/buckets/{bucket_id}/{object_uuid}` | download (public or owner) |

## Troubleshooting

- `psycopg.OperationalError` → check Postgres is running, `.env` port (default Postgres is `5432`, not `8000`), and `dbname` exists (`createdb snorlax`).
- CORS error → make sure frontend is served from `http://localhost:5500` or `http://127.0.0.1:5500`.
- Empty download / decrypt fail → wrong bucket password used at upload time.
