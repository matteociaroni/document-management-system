"""
Middleware to keep users.last_active_at updated.

Updates the column at most once every 5 minutes per user to avoid
excessive DB writes on every authenticated request.
"""

from datetime import datetime, timezone, timedelta
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.database import SessionLocal
from app.models import User

# Minimum interval between last_active_at updates per user
_UPDATE_INTERVAL = timedelta(minutes=5)

# In-memory debounce cache: {user_id_str: last_updated_datetime}
_last_updated: dict[str, datetime] = {}


class LastActiveMiddleware(BaseHTTPMiddleware):
    """Update users.last_active_at for authenticated requests, debounced to 5 minutes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only act on successful authenticated responses
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return response

        # Decode the JWT to extract user_id without re-running full auth logic
        try:
            from jose import jwt
            from app.config import settings

            token = auth_header.split(" ", 1)[1]
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
                options={"verify_exp": False},  # already verified by get_current_user
            )
            user_id: str = payload.get("sub")
            if not user_id:
                return response
        except Exception:
            return response

        # Debounce: skip if updated recently
        now = datetime.now(timezone.utc)
        last = _last_updated.get(user_id)
        if last and (now - last) < _UPDATE_INTERVAL:
            return response

        # Update DB in a short-lived session (fire-and-forget style)
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.last_active_at = now
                db.commit()
                _last_updated[user_id] = now
        except Exception:
            pass  # Never break a request due to this middleware
        finally:
            db.close()

        return response
