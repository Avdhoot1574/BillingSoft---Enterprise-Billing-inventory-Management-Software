import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.modules.audit.service import record_audit, _client_ip


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def register_user(db: Session, request: Request, *, email: str, password: str, full_name: str,
                  phone: str | None) -> dict:
    email = _normalise_email(email)
    try:
        row = db.execute(
            text(
                """INSERT INTO users (email, phone, full_name, password_hash)
                   VALUES (:email, :phone, :full_name, :hash)
                   RETURNING id, email, full_name, phone"""
            ),
            {"email": email, "phone": phone or None, "full_name": full_name.strip(), "hash": hash_password(password)},
        ).mappings().one()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "EMAIL_OR_PHONE_ALREADY_REGISTERED", "An account with this email or phone already exists")
    record_audit(db, action="user.register", entity_type="user", entity_id=row["id"],
                 actor_user_id=row["id"], request=request, after={"email": email})
    db.commit()
    return dict(row)


def _issue_session(db: Session, request: Request, user_id: uuid.UUID) -> dict:
    s = get_settings()
    refresh_plain, refresh_hash = new_refresh_token()
    session_id = db.execute(
        text(
            """INSERT INTO user_sessions (user_id, refresh_token_hash, user_agent, ip_address, expires_at)
               VALUES (:uid, :hash, :ua, CAST(:ip AS inet), :exp) RETURNING id"""
        ),
        {
            "uid": user_id,
            "hash": refresh_hash,
            "ua": (request.headers.get("user-agent") or "")[:500],
            "ip": _client_ip(request),
            "exp": datetime.now(timezone.utc) + timedelta(days=s.refresh_token_days),
        },
    ).scalar_one()
    access, expires_in = create_access_token(user_id, session_id)
    return {"access_token": access, "refresh_token": refresh_plain, "token_type": "bearer", "expires_in": expires_in}


def login(db: Session, request: Request, *, email: str, password: str) -> dict:
    s = get_settings()
    email = _normalise_email(email)
    user = db.execute(
        text(
            """SELECT id, password_hash, is_active, failed_login_count, locked_until
               FROM users WHERE lower(email) = :email"""
        ),
        {"email": email},
    ).mappings().one_or_none()

    invalid = AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password")
    if user is None or user["password_hash"] is None:
        burn_password_check(password)
        raise invalid

    now = datetime.now(timezone.utc)
    if user["locked_until"] is not None and user["locked_until"] > now:
        raise AppError(429, "ACCOUNT_LOCKED", "Too many failed attempts. Try again later.")

    if not verify_password(user["password_hash"], password) or not user["is_active"]:
        failures = user["failed_login_count"] + 1
        locked_until = now + timedelta(minutes=s.login_lockout_minutes) if failures >= s.login_max_failures else None
        db.execute(
            text("UPDATE users SET failed_login_count = :n, locked_until = :lock WHERE id = :id"),
            {"n": 0 if locked_until else failures, "lock": locked_until, "id": user["id"]},
        )
        record_audit(db, action="auth.login_failed", entity_type="user", entity_id=user["id"],
                     actor_user_id=user["id"], request=request)
        db.commit()
        raise invalid

    db.execute(
        text("UPDATE users SET failed_login_count = 0, locked_until = NULL, last_login_at = now() WHERE id = :id"),
        {"id": user["id"]},
    )
    tokens = _issue_session(db, request, user["id"])
    record_audit(db, action="auth.login", entity_type="user", entity_id=user["id"],
                 actor_user_id=user["id"], request=request)
    db.commit()
    return tokens


def refresh(db: Session, request: Request, *, refresh_token: str) -> dict:
    row = db.execute(
        text(
            """SELECT s.id, s.user_id, s.revoked_at, s.last_used_at, s.expires_at, u.is_active
               FROM user_sessions s JOIN users u ON u.id = s.user_id
               WHERE s.refresh_token_hash = :h FOR UPDATE OF s"""
        ),
        {"h": hash_token(refresh_token)},
    ).mappings().one_or_none()
    if row is None:
        raise AppError(401, "INVALID_REFRESH_TOKEN", "Invalid refresh token")
    if row["revoked_at"] is not None:
        if row["last_used_at"] is None:
            # Session ended by logout (never rotated): just reject.
            raise AppError(401, "INVALID_REFRESH_TOKEN", "Invalid refresh token")
        # A rotated token was presented again: assume theft and end every session of this user.
        db.execute(text("UPDATE user_sessions SET revoked_at = now() WHERE user_id = :u AND revoked_at IS NULL"),
                   {"u": row["user_id"]})
        record_audit(db, action="auth.refresh_reuse_detected", entity_type="user", entity_id=row["user_id"],
                     actor_user_id=row["user_id"], request=request)
        db.commit()
        raise AppError(401, "INVALID_REFRESH_TOKEN", "Invalid refresh token")
    if row["expires_at"] <= datetime.now(timezone.utc) or not row["is_active"]:
        raise AppError(401, "INVALID_REFRESH_TOKEN", "Invalid refresh token")

    db.execute(text("UPDATE user_sessions SET revoked_at = now(), last_used_at = now() WHERE id = :id"),
               {"id": row["id"]})
    tokens = _issue_session(db, request, row["user_id"])
    db.commit()
    return tokens


def logout(db: Session, request: Request, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    db.execute(text("UPDATE user_sessions SET revoked_at = now() WHERE id = :id AND user_id = :u"),
               {"id": session_id, "u": user_id})
    record_audit(db, action="auth.logout", entity_type="user", entity_id=user_id,
                 actor_user_id=user_id, request=request)
    db.commit()


def list_my_companies(db: Session, user_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        text(
            """SELECT c.id, c.tenant_id, c.name, c.gstin, c.state_code, cm.is_owner
               FROM company_memberships cm
               JOIN companies c ON c.id = cm.company_id AND c.is_active
               JOIN tenant_memberships tm ON tm.tenant_id = cm.tenant_id AND tm.user_id = cm.user_id
                                         AND tm.status = 'active'
               WHERE cm.user_id = :u AND cm.status = 'active'
               ORDER BY c.name"""
        ),
        {"u": user_id},
    ).mappings().all()
    return [dict(r) for r in rows]
