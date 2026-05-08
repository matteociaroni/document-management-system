-- Estensione moderna per UUID
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------
-- USERS
-- -----------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) DEFAULT 'USER',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        last_active_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now ()
);

-- -----------------------------
-- FOLDERS
-- -----------------------------
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES folders (id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now ()
);

-- Indice per gerarchia cartelle
CREATE INDEX idx_folders_parent_id ON folders (parent_id);

-- -----------------------------
-- DOCUMENTS
-- -----------------------------
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    folder_id UUID REFERENCES folders (id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        updated_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now ()
);

-- Indici utili
CREATE INDEX idx_documents_folder_id ON documents (folder_id);

CREATE INDEX idx_documents_owner_id ON documents (owner_id);

-- -----------------------------
-- PERMISSIONS
-- -----------------------------
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders (id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents (id) ON DELETE CASCADE,
    access_level VARCHAR(20) NOT NULL,
    shared_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        CONSTRAINT chk_permission_target CHECK (
            (
                folder_id IS NOT NULL
                AND document_id IS NULL
            )
            OR (
                folder_id IS NULL
                AND document_id IS NOT NULL
            )
        ),
        CONSTRAINT chk_access_level CHECK (access_level IN ('VIEWER', 'EDITOR'))
);

CREATE INDEX idx_permissions_user_id ON permissions (user_id);

CREATE INDEX idx_permissions_user_document ON permissions (user_id, document_id);

CREATE INDEX idx_permissions_user_folder ON permissions (user_id, folder_id);

CREATE INDEX idx_permissions_document_id ON permissions (document_id);

CREATE INDEX idx_permissions_folder_id ON permissions (folder_id);

-- -----------------------------
-- HISTORY
-- -----------------------------
CREATE TABLE history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    action VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP
    WITH
        TIME ZONE DEFAULT now ()
);

CREATE INDEX idx_history_user_id ON history (user_id);

-- -----------------------------
-- EMAIL ACCOUNTS
-- -----------------------------
CREATE TABLE email_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    email_address VARCHAR(255) NOT NULL,
    imap_host VARCHAR(255) NOT NULL,
    imap_port INTEGER DEFAULT 993,
    use_ssl BOOLEAN DEFAULT TRUE,
    auth_type VARCHAR(20) DEFAULT 'app_password',
    encrypted_credentials TEXT NOT NULL,
    oauth_provider VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP
    WITH
        TIME ZONE,
        last_uid BIGINT DEFAULT 0,
        created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        CONSTRAINT chk_auth_type CHECK (auth_type IN ('app_password', 'oauth2'))
);

CREATE INDEX idx_email_accounts_user_id ON email_accounts (user_id);

-- -----------------------------
-- EMAIL JOBS
-- -----------------------------
CREATE TABLE email_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    email_account_id UUID NOT NULL REFERENCES email_accounts (id) ON DELETE CASCADE,
    message_uid BIGINT NOT NULL,
    subject TEXT,
    sender VARCHAR(255),
    received_at TIMESTAMP
    WITH
        TIME ZONE,
        eml_storage_key TEXT,
        status VARCHAR(20) DEFAULT 'pending',
        error_message TEXT,
        created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        processed_at TIMESTAMP
    WITH
        TIME ZONE,
        CONSTRAINT chk_job_status CHECK (
            status IN ('pending', 'processing', 'done', 'failed')
        ),
        UNIQUE (email_account_id, message_uid)
);

CREATE INDEX idx_email_jobs_status ON email_jobs (status);

CREATE INDEX idx_email_jobs_account_id ON email_jobs (email_account_id);

-- -----------------------------
-- AGENT FILES
-- -----------------------------
CREATE TABLE agent_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    job_id UUID REFERENCES email_jobs (id) ON DELETE CASCADE,
    source VARCHAR(20) NOT NULL DEFAULT 'email',
    filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    content_hash VARCHAR(64),
    suggested_folder_id UUID REFERENCES folders (id) ON DELETE SET NULL,
    confidence FLOAT,
    agent_reasoning TEXT,
    document_id UUID REFERENCES documents (id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending',
    auto_filed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        CONSTRAINT chk_agent_file_status CHECK (
            status IN (
                'pending',
                'auto_filed',
                'in_inbox',
                'confirmed',
                'rejected'
            )
        ),
        CONSTRAINT chk_agent_file_source CHECK (
            source IN ('email', 'manual_upload')
        ),
        CONSTRAINT chk_agent_file_source_has_job CHECK (
            (source = 'email' AND job_id IS NOT NULL)
            OR (source = 'manual_upload' AND job_id IS NULL)
        )
);

CREATE INDEX idx_agent_files_job_id ON agent_files (job_id);

CREATE INDEX idx_agent_files_status ON agent_files (status);

CREATE INDEX idx_agent_files_content_hash ON agent_files (content_hash);

CREATE INDEX idx_agent_files_source_status ON agent_files (source, status);

-- -----------------------------
-- AGENT OPERATIONS
-- -----------------------------
CREATE TABLE agent_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid (),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    job_id UUID REFERENCES email_jobs (id),
    agent_file_id UUID REFERENCES agent_files (id),
    operation_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now (),
        CONSTRAINT chk_operation_type CHECK (
            operation_type IN (
                'email_received',
                'attachment_extracted',
                'auto_filed',
                'sent_to_inbox',
                'duplicate_skipped',
                'manual_upload_received',
                'error'
            )
        )
);

CREATE INDEX idx_agent_operations_user_id ON agent_operations (user_id);

CREATE INDEX idx_agent_operations_created_at ON agent_operations (created_at);

-- -----------------------------
-- DOMAIN BRANDING
-- -----------------------------
CREATE TABLE domain_branding (
    domain VARCHAR(255) PRIMARY KEY,
    brand_name VARCHAR(100),
    primary_color VARCHAR(20),
    logo BYTEA,
    logo_mime_type VARCHAR(100),
    updated_at TIMESTAMP
    WITH
        TIME ZONE DEFAULT now ()
);