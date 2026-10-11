from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Management")),
):
    query = db.query(models.AuditLog)
    total = query.count()
    items = (
        query.order_by(models.AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": [i.as_dict() for i in items]}
