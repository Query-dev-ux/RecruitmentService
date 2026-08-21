from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.external_candidates import router as external_candidates_router
from app.api.health import router as health_router
from app.api.providers_hh import router as providers_hh_router
from app.api.search_runs import router as search_runs_router
from app.api.search_templates import router as search_templates_router
from app.api.telegram_applications import router as telegram_applications_router
from app.logging_config import configure_logging, get_logger, log_event

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event(logger, "SERVICE_STARTED")
    yield
    log_event(logger, "SERVICE_STOPPED")


app = FastAPI(title="Recruitment Service", lifespan=lifespan)
app.include_router(health_router)
app.include_router(search_templates_router)
app.include_router(search_runs_router)
app.include_router(providers_hh_router)
app.include_router(telegram_applications_router)
app.include_router(external_candidates_router)
