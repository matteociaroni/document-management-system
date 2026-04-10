from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class BaseORMModel(BaseModel):
    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseORMModel):
    id: UUID
    username: str
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[UUID] = None


class FolderResponse(BaseORMModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    owner_id: UUID
    created_at: datetime


class DocumentUploadRequest(BaseModel):
    filename: str
    mime_type: str
    folder_id: Optional[UUID] = None


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    upload_url: str


class DocumentConfirmRequest(BaseModel):
    document_id: UUID
    size_bytes: int


class DocumentResponse(BaseORMModel):
    id: UUID
    name: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    folder_id: Optional[UUID]
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class DownloadUrlResponse(BaseModel):
    download_url: str


class PermissionCreate(BaseModel):
    user_id: UUID
    document_id: Optional[UUID] = None
    folder_id: Optional[UUID] = None
    access_level: str


class PermissionResponse(BaseORMModel):
    id: UUID
    user_id: UUID
    document_id: Optional[UUID]
    folder_id: Optional[UUID]
    access_level: str
    shared_at: datetime


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: dict = {}
