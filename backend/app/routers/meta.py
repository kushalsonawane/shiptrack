from fastapi import APIRouter, Depends

from .. import models
from ..config import settings
from ..security import get_current_user

router = APIRouter(tags=["meta"])


@router.get("/company")
def company(user: models.User = Depends(get_current_user)):
    return {
        "name": settings.company_name,
        "address": settings.company_address,
        "gstin": settings.company_gstin,
        "pan": settings.company_pan,
        "city": settings.company_city,
        "state": settings.company_state,
        "state_code": settings.company_state_code,
        "phone": settings.company_phone,
        "email": settings.company_email,
        "invoice_prefix": settings.invoice_prefix,
        "ewb_mode": settings.ewb_mode,
        "auto_ewb": settings.auto_ewb,
        "smtp_configured": bool(settings.smtp_host),
    }
