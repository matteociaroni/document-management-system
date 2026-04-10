-- Estensione moderna per UUID
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------
-- USERS
-- -----------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- -----------------------------
-- FOLDERS
-- -----------------------------
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indice per gerarchia cartelle
CREATE INDEX idx_folders_parent_id ON folders(parent_id);

-- -----------------------------
-- DOCUMENTS
-- -----------------------------
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes BIGINT NOT NULL,
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indici utili
CREATE INDEX idx_documents_folder_id ON documents(folder_id);
CREATE INDEX idx_documents_owner_id ON documents(owner_id);

-- -----------------------------
-- PERMISSIONS
-- -----------------------------
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    access_level VARCHAR(20) NOT NULL,
    shared_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

    -- almeno uno tra folder o document deve essere valorizzato
    CONSTRAINT chk_permission_target CHECK (
        folder_id IS NOT NULL OR document_id IS NOT NULL
    ),

    -- livelli accesso ammessi
    CONSTRAINT chk_access_level CHECK (
        access_level IN ('VIEWER', 'EDITOR')
    )
);

-- Indici per performance
CREATE INDEX idx_permissions_user_id ON permissions(user_id);
CREATE INDEX idx_permissions_document_id ON permissions(document_id);
CREATE INDEX idx_permissions_folder_id ON permissions(folder_id);

