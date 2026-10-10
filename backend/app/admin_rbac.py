from __future__ import annotations
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base

ACCESS_LEVELS={"NONE":0,"READ":1,"WRITE":2,"FULL":3}
ADMIN_SECTIONS={
"OVERVIEW":"Overview & Analytics",
"USERS":"Users & Packages",
"Q_ECONOMY":"Q Economy & Treasury",
"Q_FEATURE_PRICING":"Q Feature Pricing",
"Q_PREDICT":"Q Predict",
"MARKETPLACE":"Q Marketplace",
"PAYMENTS":"Payments / USDT",
"PACKAGES_REFERRALS":"Packages & Referrals",
"AUDIT_LOGS":"Audit Logs",
"SYSTEM_SETTINGS":"System / Q Settings",
"ADMIN_TEAM":"Admin Team & Roles",
}

class QAdminSectionPermission(Base):
    __tablename__="q_admin_section_permissions"
    __table_args__=(UniqueConstraint("user_id","section_key",name="uq_q_admin_section_permission"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True)
    section_key:Mapped[str]=mapped_column(String(64),index=True)
    access_level:Mapped[str]=mapped_column(String(12),default="NONE")
    granted_by_user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

def _legacy_default(role,section):
    role=(role or "").upper();section=(section or "").upper()
    if role=="MASTER_ADMIN": return "FULL"
    if section=="ADMIN_TEAM": return "NONE"
    if section=="Q_FEATURE_PRICING": return "NONE"
    if role=="FINANCE_ADMIN" and section=="PAYMENTS": return "WRITE"
    if role=="MARKETPLACE_ADMIN" and section=="MARKETPLACE": return "WRITE"
    if role=="RISK_ADMIN" and section in {"Q_PREDICT","MARKETPLACE"}: return "WRITE"
    return "READ"

def effective_access(db:Session,user_id:int,role:str,section:str)->str:
    role=(role or "").upper();section=(section or "").upper()
    if role=="MASTER_ADMIN": return "FULL"
    if section not in ADMIN_SECTIONS or section=="ADMIN_TEAM": return "NONE"
    row=db.scalar(select(QAdminSectionPermission).where(QAdminSectionPermission.user_id==user_id,QAdminSectionPermission.section_key==section))
    if row:
        if row.expires_at:
            exp=row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
            level="NONE" if exp<=datetime.now(timezone.utc) else (row.access_level or "NONE").upper()
        else: level=(row.access_level or "NONE").upper()
    else: level=_legacy_default(role,section)
    if level not in ACCESS_LEVELS: level="NONE"
    if role=="READ_ONLY" and ACCESS_LEVELS[level]>ACCESS_LEVELS["READ"]: level="READ"
    return level

def permission_map(db,user_id,role):
    return {k:effective_access(db,user_id,role,k) for k in ADMIN_SECTIONS}

def require_admin_access(db,user_id,role,section,required="READ"):
    role=(role or "").upper();section=section.upper();required=required.upper()
    if role=="MASTER_ADMIN": return "FULL"
    if role=="READ_ONLY" and ACCESS_LEVELS.get(required,99)>=ACCESS_LEVELS["WRITE"]:
        raise HTTPException(403,"Read-only admin cannot edit")
    actual=effective_access(db,user_id,role,section)
    if ACCESS_LEVELS.get(actual,0)<ACCESS_LEVELS.get(required,99):
        raise HTTPException(403,f"{required.title()} access required for {ADMIN_SECTIONS.get(section,section)}")
    return actual
