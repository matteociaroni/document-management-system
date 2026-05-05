from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


class BaseORMModel(BaseModel):
    class Config:
        from_attributes = True


from enum import Enum

class UserRole(str, Enum):
    USER = "USER"
    DOMAIN_ADMIN = "DOMAIN_ADMIN"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserResponse(BaseORMModel):
    id: UUID
    username: str
    email: str
    role: UserRole
    is_active: bool


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


class PermissionDetailResponse(BaseORMModel):
    id: UUID
    user: UserResponse
    document_id: Optional[UUID]
    folder_id: Optional[UUID]
    access_level: str
    shared_at: datetime


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: dict = {}


class MoveRequest(BaseModel):
    new_folder_id: Optional[UUID] = None


class ShareByEmailRequest(BaseModel):
    email: EmailStr
    document_id: Optional[UUID] = None
    folder_id: Optional[UUID] = None
    access_level: str


class HistoryCreate(BaseModel):
    action: str


class HistoryResponse(BaseORMModel):
    id: UUID
    user_id: UUID
    action: str
    timestamp: datetime


class AdminUpdateStatusRequest(BaseModel):
    is_active: bool


class AdminUpdateRoleRequest(BaseModel):
    role: UserRole


class DomainMetricsResponse(BaseModel):
    total_users: int
    active_users: int
    total_documents: int
    total_storage_bytes: int


# --- Email Accounts ---

class EmailAccountCreate(BaseModel):
    email_address: EmailStr
    imap_host: str
    imap_port: int = 993
    use_ssl: bool = True
    auth_type: str = "app_password"  # 'app_password' | 'oauth2'
    credentials: str  # plaintext password or OAuth token — encrypted by backend before saving
    oauth_provider: Optional[str] = None  # 'gmail' | 'outlook'


class EmailAccountUpdate(BaseModel):
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    use_ssl: Optional[bool] = None
    is_active: Optional[bool] = None
    credentials: Optional[str] = None  # if provided, re-encrypted by backend


class EmailAccountResponse(BaseORMModel):
    id: UUID
    email_address: str
    imap_host: str
    imap_port: int
    use_ssl: bool
    auth_type: str
    oauth_provider: Optional[str]
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: datetime


class EmailAccountTestResponse(BaseModel):
    success: bool
    message: str


# --- Agent Operations ---

class AgentOperationResponse(BaseORMModel):
    id: UUID
    user_id: UUID
    job_id: Optional[UUID]
    attachment_id: Optional[UUID]
    operation_type: str
    description: str
    details: Optional[dict]
    created_at: datetime


# --- Agent Proposals ---

class ProposalResponse(BaseORMModel):
    id: UUID
    filename: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    suggested_folder_id: Optional[UUID]
    confidence: Optional[float]
    agent_reasoning: Optional[str]
    document_id: Optional[UUID]
    status: str
    created_at: datetime
    # Populated via join
    suggested_folder_name: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None


class ProposalMoveRequest(BaseModel):
    folder_id: Optional[UUID] = None
