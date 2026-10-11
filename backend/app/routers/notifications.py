from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import get_current_user, require_roles
from ..services import log_audit, resend_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    q: str = "",
    status: str = "",
    channel: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Notification)
    if status:
        query = query.filter(models.Notification.status == status)
    if channel:
        query = query.filter(models.Notification.channel == channel)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(models.Notification.recipient.ilike(like), models.Notification.subject.ilike(like))
        )
    total = query.count()
    items = (
        query.order_by(models.Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    shipment_nos = {}
    shipment_ids = [n.shipment_id for n in items if n.shipment_id]
    if shipment_ids:
        for shipment in db.query(models.Shipment).filter(models.Shipment.id.in_(shipment_ids)).all():
            shipment_nos[shipment.id] = shipment.shipment_no
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{**n.as_dict(), "shipment_no": shipment_nos.get(n.shipment_id)} for n in items],
    }


@router.post("/{notification_id}/retry")
def retry_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("Admin", "Dispatch", "Sales")),
):
    note = db.get(models.Notification, notification_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    resend_notification(db, note)
    log_audit(db, user, "retry_notification", "notification", note.id, note.recipient)
    db.commit()
    db.refresh(note)
    return note.as_dict()
