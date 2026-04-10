from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Permission


def has_permission(db: Session, user_id: UUID, folder_id: UUID = None, document_id: UUID = None) -> bool:
    """
    Check if user has permission for a folder or document.
    
    Args:
        db: Database session
        user_id: User ID to check
        folder_id: Folder ID (mutually exclusive with document_id)
        document_id: Document ID (mutually exclusive with folder_id)
    
    Returns:
        True if user has permission, False otherwise
    """
    if folder_id and document_id:
        raise ValueError("Cannot check both folder and document permissions simultaneously")
    
    if not folder_id and not document_id:
        return False
    
    filters = [Permission.user_id == user_id]
    if folder_id:
        filters.append(Permission.folder_id == folder_id)
    else:
        filters.append(Permission.document_id == document_id)
    
    return db.query(Permission).filter(*filters).first() is not None
