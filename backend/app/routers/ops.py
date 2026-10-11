from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import ops
from ..database import get_db
from ..security import require_roles

router = APIRouter(prefix="/ops", tags=["ops"])


@router.post("/run-alerts")
def run_alerts_now(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Management")),
):
    """Run the scheduled alert rules immediately (delays, EWB expiry, comm failures)."""
    return ops.run_alerts(db)


@router.post("/backup")
def create_backup(user=Depends(require_roles("Admin"))):
    result = ops.backup_database()
    if result is None:
        raise HTTPException(status_code=400, detail="Backup is only available for the SQLite database")
    return result


@router.get("/export/{table}")
def export_table(
    table: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin")),
):
    """Admin-only CSV export of any table."""
    try:
        content = ops.export_table_csv(db, table)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv"},
    )
