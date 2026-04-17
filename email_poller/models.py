from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())

    email_accounts = relationship("EmailAccount", back_populates="user")
    agent_operations = relationship("AgentOperation", back_populates="user")


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
    jobs = relationship("EmailJob", back_populates="email_account")

    __table_args__ = (
        CheckConstraint("auth_type IN ('app_password', 'oauth2')", name="chk_auth_type"),
        Index("idx_email_accounts_user_id", user_id),
    )


class EmailJob(Base):
    __tablename__ = "email_jobs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email_account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
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
    agent_operations = relationship("AgentOperation", back_populates="job")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'done', 'failed')", name="chk_job_status"),
        UniqueConstraint("email_account_id", "message_uid", name="uq_email_jobs_account_uid"),
        Index("idx_email_jobs_status", status),
        Index("idx_email_jobs_account_id", email_account_id),
    )


class AgentOperation(Base):
    __tablename__ = "agent_operations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(PG_UUID(as_uuid=True), ForeignKey("email_jobs.id"), nullable=True)
    operation_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="agent_operations")
    job = relationship("EmailJob", back_populates="agent_operations")

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('email_received', 'attachment_extracted', 'auto_filed', 'sent_to_inbox', 'duplicate_skipped', 'error')",
            name="chk_operation_type",
        ),
        Index("idx_agent_operations_user_id", user_id),
        Index("idx_agent_operations_created_at", created_at),
    )
