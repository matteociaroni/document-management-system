from uuid import UUID
from sqlalchemy import Column, String, Text, BigInteger, ForeignKey, DateTime, CheckConstraint, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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
    
    folders = relationship("Folder", back_populates="owner")
    documents = relationship("Document", back_populates="owner")
    permissions = relationship("Permission", back_populates="user", cascade="all, delete-orphan")


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
