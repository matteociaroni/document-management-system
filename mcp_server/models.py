from sqlalchemy import Column, String, BigInteger, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Folder(Base):
    __tablename__ = "folders"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(255), nullable=False)
    parent_id = Column(PG_UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    owner_id = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    documents = relationship("Document", back_populates="folder")

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
    owner_id = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    folder = relationship("Folder", back_populates="documents")

    __table_args__ = (
        Index("idx_documents_folder_id", folder_id),
        Index("idx_documents_owner_id", owner_id),
    )
