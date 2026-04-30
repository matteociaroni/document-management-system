# 📂 Intelligent Document Management System (DMS)

A powerful, scalable Document Management System (DMS) enhanced with Agentic Artificial Intelligence. This application goes beyond simple file storage and organization; it automates complex workflows such as fetching invoices via email and autonomously processing documents using an AI Agent, all while maintaining complete operational transparency for the user.

---

## ✨ Key Features

- 🗂️ **Advanced Document Management**: Upload, organize (into folders), and download files. Includes a parallel chunk downloading system to maximize performance and handle large files efficiently.
- 🤖 **Agentic Artificial Intelligence**: A background AI Agent processes documents and executes automated tasks. It integrates the Model Context Protocol (MCP) for seamless interaction between the LLM and the system's data.
- 📧 **Email Automation (Invoice Poller)**: Continuous monitoring of IMAP accounts to automatically extract attachments (e.g., PDF invoices) and securely save them into the storage and database.
- 👁️ **Transparency & Agent History UI**: A user interface designed to clearly distinguish user actions from AI Agent actions. Visual badges ("unread" notifications) highlight files or folders modified by the AI, and an "Agent History" chronological view displays logs of all automated activities in real-time.
- 🔒 **Security & Robustness**: Secure handling of email credentials using encryption, strict input validation, and a solid error management system with global UI notifications (Toast UI).
- ☁️ **S3-Compatible Object Storage**: Utilizes SeaweedFS for distributed, highly scalable object storage that is fully compatible with the S3 protocol.

---

## 🏗️ Architecture & Technology Stack

The project is built on a microservices architecture entirely containerized using **Docker** and **Docker Compose**.

### System Components:
1. **Frontend (`/frontend`)**: React.js with Vite and Tailwind/Vanilla CSS. Uses React Router DOM for navigation and Lucide for iconography.
2. **Backend API (`/backend`)**: High-performance RESTful API built in Python with **FastAPI** and **SQLAlchemy**. Handles authentication, database metadata, and storage communications.
3. **Database (`postgres`)**: PostgreSQL v16 for structured and relational storage of document metadata, email accounts, and task logs.
4. **S3 Object Storage (`seaweedfs`)**: A local SeaweedFS cluster (Filer, Master, Volume, S3 Gateway) for efficient file storage.
5. **Agent Worker (`/agent_worker`)**: Asynchronous Python service (`atomic-agents`, `instructor`) that consumes events and executes intelligent tasks using LLMs (e.g., via OpenAI).
6. **MCP Server (`/mcp_server`)**: Model Context Protocol Server providing the AI Agent with the context and tools to operate on the domain data.
7. **Email Poller (`/email_poller`)**: Background worker based on `APScheduler` and `IMAPClient` to regularly synchronize mailboxes and process incoming messages.

---

## 🚀 Prerequisites

To run the application locally, ensure you have the following installed on your machine:
- **Docker** (v20.10+)
- **Docker Compose** (v2.0+)
- **Git**

---

## ⚙️ Installation & Quick Start

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd document-management-system
   ```

2. **Environment Configuration**:
   Copy the example configuration file and fill in the required values (such as your LLM API Key or custom credentials):
   ```bash
   cp .env.example .env
   ```

3. **Start the Stack with Docker Compose**:
   ```bash
   docker compose up -d
   ```
   *Note: The first launch may take several minutes as it downloads Docker images and builds the local containers.*

4. **Access the Application**:
   - **Frontend App**: `http://localhost:80`
   - **Backend API Docs (Swagger UI)**: `http://localhost:8000/docs`
   - **S3 Gateway (SeaweedFS)**: `http://localhost:8333`

---

## 🧪 How to Test the Application

Once the Docker stack is running, you can verify the system's core functionalities by following these steps:

### 1. Test Core UI & Storage
- Open `http://localhost:80` in your browser.
- Create a new folder in the dashboard.
- Upload a file (e.g., an image or PDF) into the folder.
- Download the file to verify the parallel chunk downloading is working correctly.

### 2. Test Email Invoice Polling
- Navigate to the **Email Accounts** page in the frontend.
- Add your IMAP credentials (e.g., a Gmail account with an App Password).
- Send an email with a PDF attachment to that email address.
- Wait for the scheduler to trigger, or manually click the **Sync** button in the UI.
- Return to the Document Browser and verify that the system automatically fetched the email, extracted the PDF attachment, and saved it into the application.

### 3. Test Agentic AI & Transparency UI
- Perform an action that triggers the AI agent (e.g., uploading a specific document that the agent is instructed to process or summarize).
- Wait a few moments for the `agent_worker` to complete its background job.
- Open the **Agent History** view from the sidebar to inspect the logs of the tasks the AI just performed.
- Check the Document Browser for **green badges (unread indicators)** on folders or files. These indicate directories that were modified by the AI Agent while you were away. Exploring the folder will clear the badge.

---

## 📂 Repository Structure

```plaintext
document-management-system/
├── frontend/             # React/Vite web application
├── backend/              # FastAPI server
├── agent_worker/         # Worker for the Agentic AI (LLM)
├── mcp_server/           # Model Context Protocol server for the Agent
├── email_poller/         # Worker for automatic email synchronization
├── docs/                 # Additional project documentation
├── init.sql              # Initialization script for PostgreSQL
├── docker-compose.yml    # Container orchestration configuration
└── s3.json               # Local configuration for the SeaweedFS S3 module
```

---

## 🛡️ Error Handling & Logging

The application uses a centralized Global Toast system on the frontend to clearly translate server errors (e.g., port conflicts, duplicate keys, foreign key violations) into actionable messages for the user. 
Background workers maintain detailed logs that can be inspected via Docker:
```bash
# View Agent Worker logs
docker compose logs -f agent_worker

# View Email Poller logs
docker compose logs -f email_poller
```

---

## 🤝 Development & Contributions

The development environment for each module is isolated and defines its own requirements:
- To work on the frontend, navigate to `frontend/`, run `npm install` and then `npm run dev`.
- For backend and worker components, use Python virtual environments and install the packages listed in their respective `requirements.txt` files.
