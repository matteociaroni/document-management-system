# Intelligent Document Management System (DMS)

A scalable, microservices-based Document Management System enhanced with Agentic AI. The platform supports manual and automated document ingestion (via email), full-text and semantic search, and AI-driven automatic classification — all while maintaining complete transparency over agent actions.

**Live demo**: [https://dms.matteociaroni.it](https://dms.matteociaroni.it)

> To run the system locally, switch to the `dev` branch and follow the instructions in its README.

---

## Architecture

The system is decomposed into independent microservices, each owning a specific functional area. Synchronous interactions happen via REST API; computationally expensive operations (text extraction, indexing, AI classification, email polling) are handled asynchronously by dedicated workers and event queues, so background processing never blocks user-facing requests.

![System architecture](https://raw.githubusercontent.com/matteociaroni/document-management-system/refs/heads/main/docs/images/architecture-user.svg)

![Async architecture](https://raw.githubusercontent.com/matteociaroni/document-management-system/refs/heads/main/docs/images/architecture-async.svg)

### Services

| Service | Technology | Responsibility |
|---|---|---|
| `frontend` | React + Vite | SPA — document browser, agent history, email account management |
| `backend` | FastAPI + SQLAlchemy | REST API, authentication, metadata management, storage coordination |
| `postgres` | PostgreSQL 16 | Relational storage for users, documents, folders, permissions, task logs |
| `seaweedfs` | SeaweedFS (S3-compatible) | Distributed object storage for binary file contents |
| `opensearch` | OpenSearch | Full-text and semantic (vector) search index |
| `agent_worker` | Python (`atomic-agents`, `instructor`) | Async AI agent worker for automatic document classification |
| `mcp_server` | Model Context Protocol | Exposes read-only DMS tools to the AI agent |
| `email_poller` | APScheduler + IMAPClient | Periodic IMAP polling — extracts and ingests email attachments |

---

## Document Processing Pipeline

When a file is uploaded (manually or via email), it goes through a multi-stage async pipeline:

1. **Text extraction** — Apache Tika extracts plain text from any supported format (PDF, Office, images with text, etc.), providing a uniform representation regardless of file type.
2. **Indexing** — the extracted text is indexed in OpenSearch for full-text search. Semantic embeddings are generated using `paraphrase-multilingual-MiniLM-L12-v2` and stored as vectors, enabling similarity-based retrieval alongside keyword search.
3. **AI classification** — the first 2 000 characters of extracted text are sent to the AI agent, which uses MCP tools to inspect the existing folder hierarchy and determine the most appropriate destination for the file.

---

## AI Agent & MCP

The classification agent is built with **Atomic Agents** and communicates exclusively through a **Model Context Protocol (MCP)** server. The MCP server exposes only read-only tools:

- list available directories
- get directory info (name, hierarchy)
- list files within a directory

This design keeps the agent isolated from direct system writes. Its only output is a suggested destination folder and a **confidence score** (0–1). If the confidence is below 0.8, the file is placed in an inbox area for manual review rather than being classified automatically, ensuring human oversight over uncertain decisions.

---

## Email Polling

Users can link one or more IMAP accounts. The email poller periodically connects to each account, detects new messages with attachments, and automatically saves them into the object storage and database. Credentials are stored encrypted at rest. Ingested attachments then enter the same text extraction, indexing, and classification pipeline as manually uploaded files.

---

## Search

Search is powered by OpenSearch and supports two modes:

- **Full-text search** — keyword matching over the text extracted from documents.
- **Semantic search** — vector similarity over multilingual embeddings, finding documents conceptually related to the query even without exact keyword overlap.

---

## Deployment

The system runs on **Google Cloud Platform**. Stateful components (PostgreSQL, S3-compatible object storage) use GCP managed services to delegate replication, backups, failover, and scaling.

Stateless microservices are orchestrated by **Kubernetes** on a 3-node cluster using **k3s** — a lightweight Kubernetes distribution suited for constrained infrastructure while remaining fully API-compatible with standard Kubernetes. Incoming traffic is distributed across cluster nodes by the GCP managed **load balancer**, which feeds into Kubernetes Ingress for internal routing.

![Request flow](https://raw.githubusercontent.com/matteociaroni/document-management-system/f25b4f62a83d3211dde6f70945d2da2be6c1cd4e/docs/images/request-flow.svg)

### Scalability

Load tests with Locust show the system sustains ~200 concurrent users (~100 req/s) with median latency ~200 ms and p95 < 1 s. The current bottleneck under high load is the maximum connection limit of the managed CloudSQL instance (~100 connections), not the application layer. Horizontal scaling of application pods already works correctly; resolving the bottleneck requires vertical scaling of the database tier.

![Load test results](https://raw.githubusercontent.com/matteociaroni/document-management-system/refs/heads/main/docs/images/load-test.png)

---

## Monitoring

A Fluent Bit DaemonSet collects logs and Kubernetes events from all cluster nodes, filtering for `error`/`warning` severity before forwarding them to a dedicated MCP server. A monitoring AI agent reads these events through the MCP interface (read-only), diagnoses issues, and sends a Telegram notification containing the relevant log and a suggested corrective action.

---

## Repository Structure

```
document-management-system/
├── frontend/          # React/Vite SPA
├── backend/           # FastAPI REST API
├── agent_worker/      # AI classification agent
├── mcp_server/        # MCP server (agent tools)
├── email_poller/      # IMAP polling worker
├── docs/              # Architecture diagrams and full report
├── init.sql           # PostgreSQL schema init
└── s3.json            # SeaweedFS S3 module config
```
