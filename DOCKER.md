# Docker setup for local PostgreSQL

Prerequisites:

- Docker / Docker Desktop installed and running.

Start the database and Adminer (web UI):

```powershell
docker compose up -d
```

This will:
- Run PostgreSQL on host port `5432` (data persisted to a Docker volume).
- Run Adminer on `http://localhost:8080`.

Credentials (matched to `db.py`):

- **Server:** `localhost`
- **Port:** `5432`
- **Username:** `appuser`
- **Password:** `apppassword`
- **Database:** `appdb`

Install Python requirements and create tables:

```powershell
python -m pip install -r requirements.txt
python create_tables.py
```

Stop and remove containers:

```powershell
docker compose down
```
