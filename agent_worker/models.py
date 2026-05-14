from sqlalchemy import (
    Boolean, BigInteger, Column, Float, ForeignKey,
    Integer, String, Text, DateTime, Index, UniqueConstraint, CheckConstraint,
)
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

    email_accounts = relationship("EmailAccount", back_populates="user")


class Folder(Base):
    __tablename__ = "folders"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(255), nullable=False)
    parent_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(255), nullable=False)
    mime_type = Column(String(100))
    size_bytes = Column(BigInteger, nullable=True)
    folder_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_documents_folder_id", folder_id),
        Index("idx_documents_owner_id", owner_id),
    )


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
    is_active = Column(Boolean, default=True)
    last_uid = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="email_accounts")
    jobs = relationship("EmailJob", back_populates="email_account")


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
    agent_files = relationship("AgentFile", back_populates="job")

    __table_args__ = (
        UniqueConstraint("email_account_id", "message_uid", name="uq_email_jobs_account_uid"),
        Index("idx_email_jobs_status", status),
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
    needs_classification = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("EmailJob", back_populates="agent_files")

    __table_args__ = (
        Index("idx_agent_files_job_id", job_id),
        Index("idx_agent_files_status", status),
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

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('email_received', 'attachment_extracted', 'auto_filed', 'sent_to_inbox', 'duplicate_skipped', 'manual_upload_received', 'error')",
            name="chk_operation_type",
        ),
        Index("idx_agent_operations_user_id", user_id),
    )
