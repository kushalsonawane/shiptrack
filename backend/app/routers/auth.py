from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import create_token, get_current_user, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "token": create_token(user),
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role},
    }


@router.get("/auth/me")
def me(user: models.User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
