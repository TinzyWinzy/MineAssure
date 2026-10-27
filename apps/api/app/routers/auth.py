from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    dev_login_enabled,
    get_current_user,
    memberships_of,
    verify_password,
)
from app.db import get_db
from app.models import Membership, User

router = APIRouter(prefix="/auth", tags=["auth"])


class DevLoginRequest(BaseModel):
    email: str
    password: str


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/dev-login", response_model=DevLoginResponse)
def dev_login(body: DevLoginRequest, db: Session = Depends(get_db)):
    if not dev_login_enabled():
        raise HTTPException(status_code=403, detail="dev login disabled")
    user = db.query(User).filter(User.email == body.email).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(status_code=401, detail="invalid credentials")
    ms = db.query(Membership).filter(Membership.user_id == user.id).all()
    memberships = [
        {"org_id": m.org_id, "site_id": m.site_id, "role": m.role} for m in ms
    ]
    token = create_access_token(user.id, memberships)
    return DevLoginResponse(access_token=token)


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "memberships": memberships_of(user)}
