from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.schemas import LoginIn, MeOut, RefreshIn, RegisterIn, TokenOut, UserOut
from app.core.context import CurrentUser
from app.db.session import get_db
from app.modules.identity import service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    return service.register_user(db, request, email=body.email, password=body.password,
                                 full_name=body.full_name, phone=body.phone)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    return service.login(db, request, email=body.email, password=body.password)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    return service.refresh(db, request, refresh_token=body.refresh_token)


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    service.logout(db, request, user_id=user.id, session_id=user.session_id)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    phone = db.execute(text("SELECT phone FROM users WHERE id = :u"), {"u": user.id}).scalar_one_or_none()
    return {
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name, "phone": phone},
        "companies": service.list_my_companies(db, user.id),
    }
