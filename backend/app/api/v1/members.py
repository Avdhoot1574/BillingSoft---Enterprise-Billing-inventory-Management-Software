import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.api.v1.schemas import (
    AcceptInviteIn, AcceptInviteOut, InviteOut, MemberAddIn, MemberOut, RoleChangeIn, RoleOut,
)
from app.core.context import CompanyContext, CurrentUser
from app.db.session import get_db
from app.modules.companies import service

router = APIRouter(tags=["members"])
_manage_users = require_permission("settings.users.manage")


@router.get("/roles", response_model=list[RoleOut])
def roles(ctx: CompanyContext = Depends(_manage_users), db: Session = Depends(get_db)):
    return service.list_roles(db, ctx.tenant_id)


@router.get("/members", response_model=list[MemberOut])
def members(ctx: CompanyContext = Depends(_manage_users), db: Session = Depends(get_db)):
    return service.list_members(db, ctx.company_id)


@router.post("/members/add", response_model=MemberOut, status_code=201)
def add_member_endpoint(body: MemberAddIn, request: Request, ctx: CompanyContext = Depends(_manage_users),
                        db: Session = Depends(get_db)):
    return service.add_member(db, request, ctx, name=body.name, email=body.email,
                              password=body.password, role_id=body.role_id)


@router.post("/invitations/accept", response_model=AcceptInviteOut)
def accept(body: AcceptInviteIn, request: Request, user: CurrentUser = Depends(get_current_user),
           db: Session = Depends(get_db)):
    return service.accept_invitation(db, request, user=user, token=body.token)


@router.patch("/members/{membership_id}/role", status_code=204, response_class=Response)
def change_role(membership_id: uuid.UUID, body: RoleChangeIn, request: Request,
                ctx: CompanyContext = Depends(_manage_users), db: Session = Depends(get_db)):
    service.change_member_role(db, request, ctx, membership_id=membership_id, role_id=body.role_id)


@router.delete("/members/{membership_id}", status_code=204, response_class=Response)
def remove(membership_id: uuid.UUID, request: Request, ctx: CompanyContext = Depends(_manage_users),
           db: Session = Depends(get_db)):
    service.remove_member(db, request, ctx, membership_id=membership_id)
