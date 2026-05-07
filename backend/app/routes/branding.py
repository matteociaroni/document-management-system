"""Domain branding: logo, color and name customization."""

import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import DomainBranding, User
from app.routes.admin import get_current_domain_admin, get_user_domain
from app.schemas import BrandingResponse, BrandingUpdateRequest

router = APIRouter(tags=["branding"])

MAX_LOGO_BYTES = 1_000_000  # 1 MB
ALLOWED_LOGO_MIME = {"image/png", "image/jpeg", "image/svg+xml", "image/webp", "image/gif"}
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _to_response(b: DomainBranding) -> BrandingResponse:
    return BrandingResponse(
        domain=b.domain,
        brand_name=b.brand_name,
        primary_color=b.primary_color,
        has_logo=b.logo is not None,
        updated_at=b.updated_at,
    )


def _get_or_create(db: Session, domain: str) -> DomainBranding:
    b = db.query(DomainBranding).filter(DomainBranding.domain == domain).first()
    if not b:
        b = DomainBranding(domain=domain)
        db.add(b)
        db.commit()
        db.refresh(b)
    return b


@router.get("/branding/me", response_model=BrandingResponse)
def get_my_branding(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    domain = get_user_domain(user.email)
    b = db.query(DomainBranding).filter(DomainBranding.domain == domain).first()
    if not b:
        return BrandingResponse(domain=domain)
    return _to_response(b)


@router.get("/branding/me/logo")
def get_my_logo(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    domain = get_user_domain(user.email)
    b = db.query(DomainBranding).filter(DomainBranding.domain == domain).first()
    if not b or not b.logo:
        raise HTTPException(status_code=404, detail="No logo set")
    return Response(
        content=bytes(b.logo),
        media_type=b.logo_mime_type or "application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.put("/admin/branding", response_model=BrandingResponse)
def update_branding(
    req: BrandingUpdateRequest,
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db),
):
    if req.primary_color is not None and req.primary_color != "" and not HEX_COLOR_RE.match(req.primary_color):
        raise HTTPException(status_code=400, detail="primary_color must be a hex string like #3b82f6")

    domain = get_user_domain(admin.email)
    b = _get_or_create(db, domain)

    if req.brand_name is not None:
        b.brand_name = req.brand_name.strip() or None
    if req.primary_color is not None:
        b.primary_color = req.primary_color.strip() or None

    db.commit()
    db.refresh(b)
    return _to_response(b)


@router.post("/admin/branding/logo", response_model=BrandingResponse)
async def upload_logo(
    file: UploadFile = File(...),
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db),
):
    if file.content_type not in ALLOWED_LOGO_MIME:
        raise HTTPException(status_code=400, detail=f"Unsupported logo type: {file.content_type}")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail=f"Logo exceeds {MAX_LOGO_BYTES} bytes")

    domain = get_user_domain(admin.email)
    b = _get_or_create(db, domain)
    b.logo = data
    b.logo_mime_type = file.content_type
    db.commit()
    db.refresh(b)
    return _to_response(b)


@router.delete("/admin/branding/logo", response_model=BrandingResponse)
def delete_logo(
    admin: User = Depends(get_current_domain_admin),
    db: Session = Depends(get_db),
):
    domain = get_user_domain(admin.email)
    b = _get_or_create(db, domain)
    b.logo = None
    b.logo_mime_type = None
    db.commit()
    db.refresh(b)
    return _to_response(b)
