"""LEMMIQ V2.12.3 - official support onboarding and admin-only password reset.

Passwords are never stored or returned in readable form except for the one-time
random replacement sent to the authorised Master Admin on reset. Old passwords
cannot be retrieved from existing salted PBKDF2 password hashes.
"""
from __future__ import annotations

import json
import os
import secrets
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .models import User, Chat, ChatSetting, Message
from .v28 import QAdminRole, QAdminAuditLog


def utcnow():
    return datetime.now(timezone.utc)


class UserCredentialRevisionV2123(Base):
    __tablename__ = "user_credential_revision_v2123"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def version_for_user(db: Session, user_id: int) -> int:
    state = db.get(UserCredentialRevisionV2123, user_id)
    return int(state.revision) if state else 0


def official_user(db: Session):
    # Never silently route support chats to an arbitrary account.
    expected_id = int(os.getenv("LEMMIQ_OFFICIAL_USER_ID", "22"))
    expected_username = os.getenv("LEMMIQ_OFFICIAL_USERNAME", "lemmiq").strip().lower()
    user = db.get(User, expected_id)
    if not user or user.username.strip().lower() != expected_username:
        return None
    return user


def ensure_official_chat(db: Session, new_user: User):
    """Create a visible direct thread for both sides, with one welcome message.

    Invoked only after registration commit. Idempotent if registration is retried.
    Returns a record for optional websocket notification, or None.
    """
    support = official_user(db)
    if not support or support.id == new_user.id:
        return None
    a, b = sorted((support.id, new_user.id))
    chat = db.scalar(select(Chat).where(Chat.user1_id == a, Chat.user2_id == b))
    if chat:
        return None
    chat = Chat(user1_id=a, user2_id=b)
    db.add(chat)
    db.flush()
    db.add_all([
        ChatSetting(chat_id=chat.id, user_id=a),
        ChatSetting(chat_id=chat.id, user_id=b),
    ])
    welcome = Message(
        chat_id=chat.id,
        sender_id=support.id,
        text=(
            "Welcome to LEMMIQ! 👋 This is the official support chat. "
            "If you need help with your account or Q features, message us here. "
            "For password recovery, contact support; never share your existing password."
        ),
        ai_generated=False,
    )
    db.add(welcome)
    db.flush()
    chat.updated_at = utcnow()
    return {"support_id": support.id, "message": welcome}


class ResetPasswordRequestV2123(BaseModel):
    reason: str = Field(min_length=8, max_length=300)
    confirm_username: str = Field(min_length=1, max_length=40)
    admin_password: str = Field(min_length=6, max_length=128)


def register_v2123_support(app, current_user, get_db, hash_password):
    router = APIRouter(prefix="/v2123", tags=["Official Support and Account Recovery"])

    @router.get("/support")
    def support_contact(_u: User = Depends(current_user), db: Session = Depends(get_db)):
        support = official_user(db)
        if not support:
            raise HTTPException(503, "Official support account is not configured")
        return {
            "id": support.id,
            "username": support.username,
            "display_name": support.display_name,
        }

    @router.post("/admin/users/{user_id}/reset-password")
    def admin_reset_password(
        user_id: int,
        body: ResetPasswordRequestV2123,
        admin: User = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        role = db.get(QAdminRole, admin.id)
        if not role or not role.active or role.role != "MASTER_ADMIN":
            raise HTTPException(403, "Master Admin access is required")
        admin_check, _ = hash_password(body.admin_password, admin.salt)
        if not hmac.compare_digest(admin_check, admin.password_hash):
            raise HTTPException(403, "Master Admin password verification failed")
        target = db.get(User, user_id)
        if not target:
            raise HTTPException(404, "User not found")
        if body.confirm_username.strip().lower().lstrip('@') != target.username.lower():
            raise HTTPException(422, "Confirm the exact target username")
        if target.id == admin.id:
            raise HTTPException(403, "Use a separate secure process to recover your own admin account")
        target_role = db.get(QAdminRole, target.id)
        if target_role and target_role.active:
            raise HTTPException(403, "Admin accounts cannot be reset using the support tool")

        # Row lock prevents overlapping resets on PostgreSQL.
        db.execute(select(User.id).where(User.id == target.id).with_for_update()).all()
        state = db.get(UserCredentialRevisionV2123, target.id)
        now = utcnow()
        if state and state.reset_at:
            last = state.reset_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last > now - timedelta(minutes=5):
                raise HTTPException(429, "This account was recently reset; try again later")
        if not state:
            state = UserCredentialRevisionV2123(user_id=target.id, revision=0)
            db.add(state)
        # No password is saved in plaintext, audit logs, emails or messages.
        temporary_password = secrets.token_urlsafe(22) + "!A7"
        new_hash, new_salt = hash_password(temporary_password)
        target.password_hash, target.salt = new_hash, new_salt
        state.revision = int(state.revision or 0) + 1
        state.reset_at = now
        db.add(QAdminAuditLog(
            admin_user_id=admin.id,
            action="ACCOUNT_PASSWORD_RESET_V2123",
            target_user_id=target.id,
            before_json="{}",
            after_json=json.dumps({"credential_revision": state.revision}),
            reason=body.reason.strip(),
        ))
        db.commit()
        return {
            "user_id": target.id,
            "username": target.username,
            "temporary_password": temporary_password,
            "shown_once": True,
            "sessions_revoked": True,
            "instructions": "Share privately with the verified account owner. Password is displayed only once.",
        }

    app.include_router(router)
