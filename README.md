# DMS — Local Development

This branch contains the full stack configured for local execution. For an overview of the system architecture and how it works, see the [`main` branch](https://github.com/matteociaroni/document-management-system/tree/main).

**Live demo**: [https://dms.matteociaroni.it](https://dms.matteociaroni.it)

---

## Prerequisites

- Docker (v20.10+)
- Docker Compose (v2.0+)

---

## Setup

**1. Clone the repository and switch to this branch:**

```bash
git clone https://github.com/matteociaroni/document-management-system.git
cd document-management-system
git checkout dev
```

**2. Configure environment variables:**

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

| Variable | Description |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | PostgreSQL credentials |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | SeaweedFS S3 credentials (must match `s3.json`) |
| `EMAIL_ENCRYPTION_KEY` | Key used to encrypt stored IMAP credentials |
| `MODEL_NAME` | LLM model identifier (e.g. `gemini-2.5-pro`) |
| `BASE_URL` | Base URL of the LLM API endpoint |
| `CUSTOM_API_KEY` | API key for the LLM provider |
| `VITE_API_URL` | Backend URL as seen from the browser (e.g. `http://localhost:8000`) |

**3. Start the stack:**

```bash
docker compose up -d
```

The first run takes a few minutes to pull images and build local containers.

---

## Endpoints

| Service | URL |
|---|---|
| Frontend | http://localhost:80 |
| Backend API (Swagger) | http://localhost:8000/docs |
| SeaweedFS S3 Gateway | http://localhost:8333 |
| Apache Tika | http://localhost:9998 |
| OpenSearch | http://localhost:9200 |

---

## Logs

```bash
docker compose logs -f agent_worker
docker compose logs -f email_poller
docker compose logs -f backend
```
