from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


def require_service_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Auth dependency for internal endpoints (everything except /health).

    CRM (or any other internal caller) must send:
        Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
    Not yet applied to any route — no business endpoints exist yet.
    """
    if credentials is None or credentials.credentials != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing service token")
