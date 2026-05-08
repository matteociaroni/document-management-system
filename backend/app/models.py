from uuid import UUID
from sqlalchemy import Column, String, Text, BigInteger, Integer, Float, ForeignKey, DateTime, CheckConstraint, Index, Boolean, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    username = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(20), default="USER")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())
    
    folders = relationship("Folder", back_populates="owner")
    documents = relationship("Document", back_populates="owner")
    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan")
    email_accounts = relationship("EmailAccount", back_populates="user", cascade="all, delete-orphan")
    agent_operations = relationship("AgentOperation", back_populates="user", cascade="all, delete-orphan")


class Folder(Base):
    __tablename__ = "folders"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(255), nullable=False)
    parent_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="folders")
    documents = relationship("Document", back_populates="folder", cascade="all, delete-orphan")
    permissions = relationship("Permission", back_populates="folder", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_folders_parent_id", parent_id),
    )


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(255), nullable=False)
    mime_type = Column(String(100))
    size_bytes = Column(BigInteger, nullable=True)
    folder_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    owner = relationship("User", back_populates="documents")
    folder = relationship("Folder", back_populates="documents")
    permissions = relationship("Permission", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_documents_folder_id", folder_id),
        Index("idx_documents_owner_id", owner_id),
    )


class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    document_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    access_level = Column(String(20), nullable=False)
    shared_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="permissions")
    folder = relationship("Folder", back_populates="permissions")
    document = relationship("Document", back_populates="permissions")
    
    __table_args__ = (
        CheckConstraint(
            "(folder_id IS NOT NULL AND document_id IS NULL) OR (folder_id IS NULL AND document_id IS NOT NULL)",
            name="chk_permission_target"
        ),
        CheckConstraint(
            "access_level IN ('VIEWER', 'EDITOR')",
            name="chk_access_level"
        ),
        Index("idx_permissions_user_id", user_id),
        Index("idx_permissions_user_document", user_id, document_id),
        Index("idx_permissions_user_folder", user_id, folder_id),
        Index("idx_permissions_document_id", document_id),
        Index("idx_permissions_folder_id", folder_id),
    )


class History(Base):
    __tablename__ = "history"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="history_entries")


class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email_address = Column(String(255), nullable=False)
    imap_host = Column(String(255), nullable=False)
    imap_port = Column(Integer, default=993)
    use_ssl = Column(Boolean, default=True)
    auth_type = Column(String(20), default="app_password")
    encrypted_credentials = Column(Text, nullable=False)
    oauth_provider = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_uid = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="email_accounts")
    jobs = relationship("EmailJob", back_populates="email_account", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "auth_type IN ('app_password', 'oauth2')",
            name="chk_auth_type"
        ),
        Index("idx_email_accounts_user_id", user_id),
    )


class EmailJob(Base):
    __tablename__ = "email_jobs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email_account_id = Column(PG_UUID(as_uuid=True), ForeignKey("email_accounts.id", ondelete="CASCADE"), nullable=False)
    message_uid = Column(BigInteger, nullable=False)
    subject = Column(Text, nullable=True)
    sender = Column(String(255), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    eml_storage_key = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    email_account = relationship("EmailAccount", back_populates="jobs")
    agent_files = relationship("AgentFile", back_populates="job", cascade="all, delete-orphan")
    agent_operations = relationship("AgentOperation", back_populates="job")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed')",
            name="chk_job_status"
        ),
        UniqueConstraint("email_account_id", "message_uid", name="uq_email_jobs_account_uid"),
        Index("idx_email_jobs_status", status),
        Index("idx_email_jobs_account_id", email_account_id),
    )


class AgentFile(Base):
    __tablename__ = "agent_files"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    job_id = Column(PG_UUID(as_uuid=True), ForeignKey("email_jobs.id", ondelete="CASCADE"), nullable=True)
    source = Column(String(20), nullable=False, default="email")
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    content_hash = Column(String(64), nullable=True)
    suggested_folder_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    confidence = Column(Float, nullable=True)
    agent_reasoning = Column(Text, nullable=True)
    document_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="pending")
    auto_filed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("EmailJob", back_populates="agent_files")
    suggested_folder = relationship("Folder", foreign_keys=[suggested_folder_id])
    document = relationship("Document", foreign_keys=[document_id])
    agent_operations = relationship("AgentOperation", back_populates="agent_file")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'auto_filed', 'in_inbox', 'confirmed', 'rejected')",
            name="chk_attachment_status"
        ),
        CheckConstraint(
            "source IN ('email', 'manual_upload')",
            name="chk_attachment_source"
        ),
        Index("idx_agent_files_job_id", job_id),
        Index("idx_agent_files_status", status),
        Index("idx_agent_files_content_hash", content_hash),
        Index("idx_agent_files_source_status", source, status),
    )


class AgentOperation(Base):
    __tablename__ = "agent_operations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(PG_UUID(as_uuid=True), ForeignKey("email_jobs.id"), nullable=True)
    agent_file_id = Column(PG_UUID(as_uuid=True), ForeignKey("agent_files.id"), nullable=True)
    operation_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="agent_operations")
    job = relationship("EmailJob", back_populates="agent_operations")
    agent_file = relationship("AgentFile", back_populates="agent_operations")

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('email_received', 'attachment_extracted', 'auto_filed', 'sent_to_inbox', 'duplicate_skipped', 'error')",
            name="chk_operation_type"
        ),
        Index("idx_agent_operations_user_id", user_id),
        Index("idx_agent_operations_created_at", created_at),
    )


class DomainBranding(Base):
    __tablename__ = "domain_branding"

    domain = Column(String(255), primary_key=True)
    brand_name = Column(String(100), nullable=True)
    primary_color = Column(String(20), nullable=True)
    logo = Column(LargeBinary, nullable=True)
    logo_mime_type = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
