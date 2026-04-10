
# API Reference - Document Management System (MVP)

> **Last Updated**: 2026-04-10

## Authentication

### POST /auth/register

User registration.

Request:

```json
{
  "username": "mario",
  "email": "mario@azienda.com",
  "password": "password123"
}
```

Response:

```json
{
  "id": "uuid",
  "username": "mario",
  "email": "mario@azienda.com"
}

```

### POST /auth/login

User login (credentials in request body).

**Request:**

```json
{
  "email": "mario@azienda.com",
  "password": "password123"
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials
- `400 Bad Request`: Missing required fields

### GET /auth/me

Returns the authenticated user (JWT required).

Response:

```json
{
  "id": "uuid",
  "email": "mario@azienda.com",
  "username": "mario"
}
```

### POST /auth/logout

Invalidates the session on the client side or server side (optional implementation).

## Health

### GET /health

Service health check.

Response:

```json
{
  "status": "ok"
}
```

## Folders

### POST /folders

Create a folder.

Request:

```json
{
  "name": "Projects",
  "parent_id": null
}

```

### GET /folders

List folders owned by current user with optional pagination.

**Query Parameters:**
- `parent_id` (optional): UUID of parent folder to filter by
- `limit` (optional, default: 20, max: 100): Number of results to return
- `offset` (optional, default: 0): Number of results to skip

**Response (200 OK):**

```json
[
  {
    "id": "uuid",
    "name": "Projects",
    "parent_id": null,
    "owner_id": "uuid",
    "created_at": "2026-04-10T11:00:00Z"
  }
]
```

**Requires:** JWT token (Bearer header)
    

### GET /folders/{id}

Get folder details (requires ownership or explicit permission).

**Response (200 OK):**

```json
{
  "id": "uuid",
  "name": "Projects",
  "parent_id": null,
  "owner_id": "uuid",
  "created_at": "2026-04-10T11:00:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Folder doesn't exist
- `403 Forbidden`: No access to folder

**Requires:** JWT token

### DELETE /folders/{id}

Delete a folder (cascades to delete all contained documents and related permissions).

**Response (204 No Content)**

**Error Responses:**
- `404 Not Found`: Folder doesn't exist
- `403 Forbidden`: Only owner can delete

**Requires:** JWT token

## Documents

### POST /documents/upload

Generate a signed upload URL and create document record.

Request (multipart/form-data):

```
file: <binary file>
folder_id: "uuid" (optional)
```

Response:

```json
{
  "document_id": "uuid",
  "upload_url": "signed-url"
}
```

### POST /documents/{document_id}/confirm

Confirm file upload to storage and finalize document.

Response (200 OK):

```json
{
  "id": "uuid",
  "name": "file.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 12345,
  "folder_id": "uuid",
  "owner_id": "uuid",
  "created_at": "2026-04-10T11:00:00Z",
  "updated_at": "2026-04-10T11:00:00Z"
}
```

### GET /documents

List documents owned by current user with pagination.

**Query Parameters:**
- `folder_id` (optional): UUID of folder to filter by
- `limit` (optional, default: 20, max: 100): Number of results to return
- `offset` (optional, default: 0): Number of results to skip

**Response (200 OK):**

```json
[
  {
    "id": "uuid",
    "name": "file.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 12345,
    "folder_id": "uuid",
    "owner_id": "uuid",
    "created_at": "2026-04-10T11:00:00Z",
    "updated_at": "2026-04-10T11:00:00Z"
  }
]
```

**Requires:** JWT token


### GET /documents/{id}

Get document details (requires ownership or explicit permission).

**Response (200 OK):**

```json
{
  "id": "uuid",
  "name": "file.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 12345,
  "folder_id": "uuid",
  "owner_id": "uuid",
  "created_at": "2026-04-10T11:00:00Z",
  "updated_at": "2026-04-10T11:00:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Document doesn't exist
- `403 Forbidden`: No access to document

**Requires:** JWT token

### GET /documents/{id}/download

Download a document via streaming response.

**Response (200 OK):** Binary file stream with appropriate Content-Type header

**Error Responses:**
- `404 Not Found`: Document doesn't exist
- `403 Forbidden`: No access to document

**Requires:** JWT token

### DELETE /documents/{id}

Delete a document (cascades to delete related permissions).

**Response (204 No Content)**

**Error Responses:**
- `404 Not Found`: Document doesn't exist
- `403 Forbidden`: Only owner can delete

**Requires:** JWT token

## Permissions

### POST /permissions

Share a document or folder with another user.

**Request:**

```json
{
  "user_id": "uuid",
  "document_id": "uuid or null",
  "folder_id": "uuid or null",
  "access_level": "VIEWER"
}
```

**Response (200 OK):**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "document_id": "uuid or null",
  "folder_id": "uuid or null",
  "access_level": "VIEWER",
  "shared_at": "2026-04-10T11:00:00Z"
}
```

**Validation Rules:**
- Exactly one of `document_id` or `folder_id` must be provided
- `access_level` must be "VIEWER" or "EDITOR"
- Requester must own the shared resource

**Error Responses:**
- `400 Bad Request`: Invalid parameters or both/neither id provided
- `403 Forbidden`: Cannot share resource you don't own
- `404 Not Found`: Resource doesn't exist

**Requires:** JWT token

### GET /permissions

List permissions granted TO current user (documents/folders shared with them).

**Response (200 OK):**

```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "document_id": "uuid or null",
    "folder_id": "uuid or null",
    "access_level": "VIEWER",
    "shared_at": "2026-04-10T11:00:00Z"
  }
]
```

**Requires:** JWT token


### DELETE /permissions/{id}

Revoke a permission (only resource owner can revoke).

**Response (204 No Content)**

**Error Responses:**
- `404 Not Found`: Permission doesn't exist
- `403 Forbidden`: Only owner of the shared resource can revoke

**Requires:** JWT token

----------

## Error Handling

Standard error format:

```json
{
  "error": "Forbidden",
  "code": "PERMISSION_DENIED",
  "details": {}
}
```
----------

## Authentication Rules

All endpoints except:

-   POST /auth/login
    
-   POST /auth/register
    
-   GET /health
    

require:

-   Valid JWT token
    
-   Ownership or permission validation
    

----------

## Business Rules

Storage model:

-   Bucket is derived from email domain (e.g. company.com)
    
-   SeaweedFS key equals document_id
    
-   No bucket management endpoints exposed
    

Access control:

-   Users can access their own documents
    
-   Users can access shared documents via permissions
    

----------

## Pagination

Applied to:

-   GET /documents
    
-   GET /folders
    

Parameters:

-   limit (default 20)
    
-   offset (default 0)
    

----------

## Upload Flow

1.  POST /documents/upload (multipart form data with file)
    
2.  Direct upload to SeaweedFS using presigned URL
    
3.  POST /documents/{document_id}/confirm
    

----------

## Download Flow

1.  GET /documents/{id}/download
    
2.  Client receives file stream directly from backend

----------

## Important Implementation Notes

### Permission Model
- **Permission.user_id** = user TO WHOM access is granted (not who granted it)
- Users can access resources if:
  - They are the owner, OR
  - They have an explicit permission record
- Permission revocation: Only resource owner can revoke permissions

### Document Lifecycle
1. POST /documents/upload → Creates document with `size_bytes=NULL`, returns presigned URL
2. Client uploads file directly to S3/SeaweedFS using presigned URL
3. POST /documents/{document_id}/confirm → Sets `size_bytes` and finalizes record

### Multi-Tenancy
- Tenant derived from email domain (e.g., `mario@company.com` → bucket: `company-com`)
- Each user's documents isolated by tenant
- Sharing works across email domains within same deployment

### Response Consistency
- All date fields in ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
- All UUIDs in standard format (36 chars with hyphens)
- Cascading deletes: folders → documents → permissions; documents → permissions

### Authentication
- JWT tokens in `Authorization: Bearer <token>` header
- Tokens expire after 24 hours
- Endpoints requiring auth will return `401 Unauthorized` if token missing/invalid
