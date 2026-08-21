import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ProviderAccount, ProviderToken, SearchTemplate
from app.db.models.enums import ProviderAccountStatus, ProviderType, SearchRunTrigger
from app.repositories import search_runs as search_runs_repo
from app.worker import get_connected_hh_access_token, process_one_run


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_get_connected_hh_access_token_returns_none_when_no_account(db_session: AsyncSession):
    token = await get_connected_hh_access_token(db_session)

    assert token is None


async def test_get_connected_hh_access_token_ignores_disconnected_accounts(db_session: AsyncSession):
    account = ProviderAccount(provider=ProviderType.HH, status=ProviderAccountStatus.DISCONNECTED)
    db_session.add(account)
    await db_session.commit()
    db_session.add(ProviderToken(provider_account_id=account.id, access_token="secret"))
    await db_session.commit()

    token = await get_connected_hh_access_token(db_session)

    assert token is None


async def test_get_connected_hh_access_token_returns_token_for_connected_account(db_session: AsyncSession):
    account = ProviderAccount(provider=ProviderType.HH, status=ProviderAccountStatus.CONNECTED)
    db_session.add(account)
    await db_session.commit()
    db_session.add(ProviderToken(provider_account_id=account.id, access_token="live-token"))
    await db_session.commit()

    token = await get_connected_hh_access_token(db_session)

    assert token == "live-token"


async def test_process_one_run_does_nothing_for_unknown_run(db_session: AsyncSession):
    import uuid

    await process_one_run(db_session, uuid.uuid4())  # should not raise


async def test_process_one_run_fails_when_template_missing(db_session: AsyncSession):
    import uuid

    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=uuid.uuid4(), trigger=SearchRunTrigger.MANUAL
    )

    await process_one_run(db_session, run.id)

    refreshed = await search_runs_repo.get_search_run(db_session, run.id)
    assert refreshed.status.value == "failed"
    assert "template" in refreshed.error_message


async def test_process_one_run_fails_when_no_hh_account_connected(db_session: AsyncSession):
    template = SearchTemplate(name="Media Buyer")
    db_session.add(template)
    await db_session.commit()
    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )

    await process_one_run(db_session, run.id)

    refreshed = await search_runs_repo.get_search_run(db_session, run.id)
    assert refreshed.status.value == "failed"
    assert "connected HH account" in refreshed.error_message


@pytest.mark.respx(base_url="https://api.hh.ru")
async def test_process_one_run_completes_with_connected_account(db_session: AsyncSession, respx_mock):
    respx_mock.get("/resumes").mock(return_value=httpx.Response(200, json={"items": [], "pages": 0}))

    account = ProviderAccount(provider=ProviderType.HH, status=ProviderAccountStatus.CONNECTED)
    db_session.add(account)
    await db_session.commit()
    db_session.add(ProviderToken(provider_account_id=account.id, access_token="live-token"))
    template = SearchTemplate(name="Media Buyer")
    db_session.add(template)
    await db_session.commit()
    run = await search_runs_repo.create_search_run(
        db_session, search_template_id=template.id, trigger=SearchRunTrigger.MANUAL
    )

    await process_one_run(db_session, run.id)

    refreshed = await search_runs_repo.get_search_run(db_session, run.id)
    assert refreshed.status.value == "completed"
    assert refreshed.stats == {"found": 0, "new": 0, "known": 0, "passed_hard_filters": 0, "above_threshold": 0}
