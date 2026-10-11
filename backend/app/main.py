import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, ops, seed
from .database import Base, SessionLocal, engine
from .routers import (
    audit,
    auth,
    dashboard,
    documents,
    eway,
    imports,
    invoices,
    meta,
    notifications,
    parties,
    reports,
    search,
    shipments,
)
from .routers import ops as ops_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed.ensure_seed(db)
    finally:
        db.close()

    task = None
    if config.settings.background_jobs:
        task = asyncio.create_task(_background_ops())
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _background_ops():
    """Scheduled operations: daily database backups and the alert rules from the project document."""

    def cycle():
        try:
            if ops.backup_due():
                ops.backup_database()
        except Exception:
            pass
        db = SessionLocal()
        try:
            ops.run_alerts(db)
        except Exception:
            pass
        finally:
            db.close()

    await asyncio.sleep(3)
    await asyncio.to_thread(cycle)
    interval = max(5, config.settings.alert_interval_minutes) * 60
    while True:
        await asyncio.sleep(interval)
        await asyncio.to_thread(cycle)


app = FastAPI(title="Shipment Tracker API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api"

app.include_router(auth.router, prefix=API)
app.include_router(parties.customer_router, prefix=API)
app.include_router(parties.vendor_router, prefix=API)
app.include_router(parties.transporters_router, prefix=API)
app.include_router(parties.vehicles_router, prefix=API)
app.include_router(invoices.router, prefix=API)
app.include_router(eway.router, prefix=API)
app.include_router(shipments.router, prefix=API)
app.include_router(search.router, prefix=API)
app.include_router(dashboard.router, prefix=API)
app.include_router(notifications.router, prefix=API)
app.include_router(reports.router, prefix=API)
app.include_router(documents.router, prefix=API)
app.include_router(meta.router, prefix=API)
app.include_router(imports.router, prefix=API)
app.include_router(audit.router, prefix=API)
app.include_router(ops_router.router, prefix=API)


@app.get("/api/health")
def health():
    return {"status": "ok"}
