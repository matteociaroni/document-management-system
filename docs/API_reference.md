
# API Reference - Document Management System (MVP)

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

User login.

Request:

```json
{
  "email": "mario@azienda.com",
  "password": "password123"
}

```

Response:

```json
{
  "access_token": "jwt",
  "token_type": "bearer"
}

```

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

List folders.

Query parameters:

-   parent_id (optional)
    

### GET /folders/{id}

Get folder details.

### DELETE /folders/{id}

Delete a folder (cascade optional).

## Documents

### POST /documents/upload-url

Generate a signed upload URL.

Request:

```json
{
  "filename": "file.pdf",
  "mime_type": "application/pdf",
  "folder_id": "uuid"
}
```

Response:

```json
{
  "document_id": "uuid",
  "upload_url": "signed-url"
}
```

### POST /documents/confirm

Confirm file upload to storage.

Request:

```json
{
  "document_id": "uuid",
  "size_bytes": 12345
}
```

### GET /documents

List documents.

Query parameters:

-   folder_id
    
-   limit
    
-   offset


### GET /documents/{id}

Get document details.

Response:

```json
{
  "id": "uuid",
  "name": "file.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 12345,
  "folder_id": "uuid",
  "owner_id": "uuid"
}
```

### GET /documents/{id}/download-url

Generate a signed download URL.

Response:

```json
{
  "download_url": "signed-url"
}
```

### DELETE /documents/{id}

Delete a document.

## Permissions

### POST /permissions

Share a document or folder.

Request:

```json
{
  "user_id": "uuid",
  "document_id": "uuid|null",
  "folder_id": "uuid|null",
  "access_level": "VIEWER"
}
```

### GET /permissions

List permissions.


### DELETE /permissions/{id}

Remove a permission.

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

### Common status codes

Code

Description

400

Bad Request

401

Unauthorized

403

Forbidden

404

Not Found

500

Internal Server Error

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

1.  POST /documents/upload-url
    
2.  Direct upload to SeaweedFS
    
3.  POST /documents/confirm
    

----------

## Download Flow

1.  GET /documents/{id}/download-url
    
2.  Client downloads from SeaweedFS using signed URL
