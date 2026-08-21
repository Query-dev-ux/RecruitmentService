import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_service_token
from app.db.base import get_db
from app.db.models import ProviderAccount, ProviderToken
from app.db.models.enums import ProviderAccountStatus, ProviderType
from app.providers.hh.auth import build_authorize_url, exchange_code_for_token
from app.schemas.provider import HHConnectOut, HHStatusOut

router = APIRouter(prefix="/providers/hh", tags=["providers-hh"])


async def _get_hh_account(db: AsyncSession) -> ProviderAccount | None:
    result = await db.execute(
        select(ProviderAccount).where(ProviderAccount.provider == ProviderType.HH).order_by(ProviderAccount.updated_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/status", response_model=HHStatusOut)
async def hh_status(
    _: None = Depends(require_service_token),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_hh_account(db)
    if account is None:
        return HHStatusOut(connected=False)
    return HHStatusOut(
        connected=account.status == ProviderAccountStatus.CONNECTED,
        account_id=account.id,
        label=account.label,
        status=account.status,
        connected_at=account.connected_at,
    )


@router.post("/connect", response_model=HHConnectOut)
async def hh_connect(_: None = Depends(require_service_token)):
    # `state` is generated but not yet persisted/verified against the
    # callback — CSRF-state verification for this flow is a known gap to
    # close before going live, not silently skipped. Also see the note on
    # /callback below re: this endpoint's reachability.
    state = secrets.token_urlsafe(24)
    return HHConnectOut(authorize_url=build_authorize_url(state))


@router.get("/callback")
async def hh_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """No require_service_token here on purpose: this is the actual OAuth
    redirect target the user's browser lands on after approving access on
    hh.ru — a browser navigation can't attach our internal bearer token.
    The `code` itself (plus, once implemented, `state` verification) is
    what secures this endpoint, per standard OAuth practice.

    Deployment note: recruitment-api currently has no port published to the
    host (see docker-compose.yml) — this endpoint needs to be reachable
    from wherever HH_REDIRECT_URI points, which likely means either
    publishing just this path through a reverse proxy, or having CRM (which
    is presumably public-facing already) receive the redirect on its own
    domain and forward the code here over the internal network. Which of
    those applies depends on the production server's setup — flagged, not
    decided here.
    """
    try:
        token_response = await exchange_code_for_token(code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange HH authorization code"
        ) from exc

    account = await _get_hh_account(db)
    if account is None:
        account = ProviderAccount(provider=ProviderType.HH)
        db.add(account)
        await db.flush()

    account.status = ProviderAccountStatus.CONNECTED
    account.connected_at = datetime.now(timezone.utc)

    expires_in = token_response.get("expires_in")
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None

    db.add(
        ProviderToken(
            provider_account_id=account.id,
            access_token=token_response["access_token"],
            refresh_token=token_response.get("refresh_token"),
            expires_at=expires_at,
        )
    )
    await db.commit()
    return {"status": "connected"}
