from __future__ import annotations
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base

LEVELS={"NONE":0,"READ":1,"WRITE":2,"FULL":3}
SECTIONS=[
    "OVERVIEW","USERS","Q_ECONOMY","Q_USAGE","Q_FEATURE_PRICING","Q_PREDICT",
    "MARKETPLACE","PAYMENTS","PACKAGES_REFERRALS","NOTIFICATIONS_SUPPORT",
    "TRUST_BUSINESS","CALLS_MEETINGS","SYSTEM_SETTINGS","AUDIT_LOGS","ADMIN_TEAM"
]

class AdminSectionPermission(Base):
    __tablename__="admin_section_permissions"
    __table_args__=(UniqueConstraint("user_id","section_key",name="uq_admin_user_section"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    section_key:Mapped[str]=mapped_column(String(60),index=True)
    access_level:Mapped[str]=mapped_column(String(12),default="NONE")
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    granted_by:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class AdminPermissionAudit(Base):
    __tablename__="admin_permission_audit"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    admin_user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    target_user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    section_key:Mapped[str]=mapped_column(String(60),default="")
    before_level:Mapped[str]=mapped_column(String(12),default="NONE")
    after_level:Mapped[str]=mapped_column(String(12),default="NONE")
    details_json:Mapped[str]=mapped_column(Text,default="{}")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),index=True)

def permission_level(db:Session,user_id:int,section:str)->str:
    row=db.scalar(select(AdminSectionPermission).where(
        AdminSectionPermission.user_id==user_id,
        AdminSectionPermission.section_key==section.upper()
    ))
    if not row:return "NONE"
    if row.expires_at:
        exp=row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        if exp<=datetime.now(timezone.utc):return "NONE"
    level=(row.access_level or "NONE").upper()
    return level if level in LEVELS else "NONE"

def has_permission(db:Session,user_id:int,section:str,required:str)->bool:
    return LEVELS.get(permission_level(db,user_id,section),0)>=LEVELS.get(required.upper(),99)

def require_permission(db:Session,user_id:int,section:str,required:str):
    if not has_permission(db,user_id,section,required):
        raise HTTPException(403,f"{required.title()} access required for {section.replace('_',' ').title()}")

def section_for_path(path:str)->str:
    p=path.lower()
    if "/admin/roles" in p or "/v2108/admin/access" in p:return "ADMIN_TEAM"
    if "q-features" in p:return "Q_FEATURE_PRICING"
    if "predict" in p:return "Q_PREDICT"
    if "payment-wallet" in p or "payment-order" in p:return "PAYMENTS"
    if "market" in p:return "MARKETPLACE"
    if "referral" in p or "package" in p or "subscription" in p:return "PACKAGES_REFERRALS"
    if "audit" in p:return "AUDIT_LOGS"
    if "treasury" in p or "wallet" in p:return "Q_ECONOMY"
    if "users" in p:return "USERS"
    return "OVERVIEW"
