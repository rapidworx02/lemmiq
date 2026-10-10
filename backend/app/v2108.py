from __future__ import annotations
import json, csv, io, math
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from .models import User
from .v28 import QAdminRole, QSubscriptionLot, PACKAGE_PLANS
from .v2105_q_features import QFeatureUsage, QFeatureTierRule, FEATURES, Q_MICROS, _tier_code
from .v29 import ShadowMonetisationEvent
from .admin_permissions import AdminSectionPermission, AdminPermissionAudit, SECTIONS, LEVELS, permission_level

def now(): return datetime.now(timezone.utc)

class PermissionItem(BaseModel):
    section_key:str
    access_level:str
    expires_at:datetime|None=None

class PermissionUpdate(BaseModel):
    username:str
    base_role:str="SUPPORT_ADMIN"
    active:bool=True
    permissions:list[PermissionItem]

def register_v2108(app,current_user,get_db):
    router=APIRouter(prefix="/v2108",tags=["LEMMIQ V2.10.8"])

    def role(db,u):
        r=db.get(QAdminRole,u.id)
        if not r or not r.active: raise HTTPException(403,"Admin access required")
        return r
    def master(u=Depends(current_user),db:Session=Depends(get_db)):
        r=role(db,u)
        if r.role!="MASTER_ADMIN":raise HTTPException(403,"Master Admin access required")
        return u
    def admin(u=Depends(current_user),db:Session=Depends(get_db)):
        role(db,u);return u

    @router.get("/admin/access/search")
    def search_user(username:str,u=Depends(master),db:Session=Depends(get_db)):
        q=username.strip().lstrip("@").lower()
        x=db.scalar(select(User).where(func.lower(User.username)==q))
        if not x: raise HTTPException(404,"LEMMIQ user not found")
        r=db.get(QAdminRole,x.id)
        perms={s:permission_level(db,x.id,s) for s in SECTIONS}
        return {"user":{"id":x.id,"username":x.username,"display_name":x.display_name},
                "role":r.role if r and r.active else None,"active":bool(r and r.active),"permissions":perms}

    @router.get("/admin/access")
    def access_list(u=Depends(master),db:Session=Depends(get_db)):
        rows=db.scalars(select(QAdminRole).where(QAdminRole.active.is_(True))).all()
        out=[]
        for r in rows:
            x=db.get(User,r.user_id)
            if not x:continue
            out.append({"user_id":x.id,"username":x.username,"display_name":x.display_name,
                        "role":r.role,"permissions":{s:permission_level(db,x.id,s) for s in SECTIONS}})
        return {"sections":SECTIONS,"items":out}

    @router.put("/admin/access")
    def save_access(body:PermissionUpdate,u=Depends(master),db:Session=Depends(get_db)):
        q=body.username.strip().lstrip("@").lower()
        x=db.scalar(select(User).where(func.lower(User.username)==q))
        if not x:raise HTTPException(404,"LEMMIQ user not found")
        if x.id==u.id and (body.base_role!="MASTER_ADMIN" or not body.active):
            raise HTTPException(409,"Current Master Admin cannot demote or disable itself")
        base=body.base_role.strip().upper()
        if base=="MASTER_ADMIN" and x.id!=u.id:
            raise HTTPException(403,"Additional Master Admin assignment requires direct security review")
        r=db.get(QAdminRole,x.id)
        if not r:r=QAdminRole(user_id=x.id,role=base,active=body.active);db.add(r)
        else:r.role=base;r.active=body.active
        sent=set()
        for item in body.permissions:
            sec=item.section_key.strip().upper();lvl=item.access_level.strip().upper()
            if sec not in SECTIONS or lvl not in LEVELS:raise HTTPException(422,"Invalid section/access level")
            if sec=="ADMIN_TEAM" and lvl!="NONE": raise HTTPException(403,"Admin Team & Roles is Master Admin only")
            sent.add(sec)
            row=db.scalar(select(AdminSectionPermission).where(AdminSectionPermission.user_id==x.id,AdminSectionPermission.section_key==sec))
            before=(row.access_level if row else "NONE")
            if not row:
                row=AdminSectionPermission(user_id=x.id,section_key=sec);db.add(row)
            row.access_level=lvl;row.expires_at=item.expires_at;row.granted_by=u.id;row.updated_at=now()
            db.add(AdminPermissionAudit(admin_user_id=u.id,target_user_id=x.id,section_key=sec,before_level=before,after_level=lvl,
                                        details_json=json.dumps({"expires_at":item.expires_at.isoformat() if item.expires_at else None})))
        db.commit()
        return {"ok":True,"user_id":x.id,"username":x.username,"role":r.role,
                "permissions":{s:permission_level(db,x.id,s) for s in SECTIONS}}

    def since_for(period:str,days:int|None=None):
        p=period.lower()
        if p=="today":
            n=now();return n.replace(hour=0,minute=0,second=0,microsecond=0)
        if p=="7d":return now()-timedelta(days=7)
        if p=="30d":return now()-timedelta(days=30)
        if p=="90d":return now()-timedelta(days=90)
        if p=="365d":return now()-timedelta(days=365)
        return now()-timedelta(days=days or 30)

    @router.get("/admin/q-usage")
    def q_usage(period:str="30d",username:str="",tier:str="",feature:str="",u=Depends(admin),db:Session=Depends(get_db)):
        if db.get(QAdminRole,u.id).role!="MASTER_ADMIN" and permission_level(db,u.id,"Q_USAGE")=="NONE":
            raise HTTPException(403,"Q Usage Analytics access required")
        start=since_for(period)
        stmt=select(QFeatureUsage).where(QFeatureUsage.created_at>=start)
        if feature.strip():stmt=stmt.where(QFeatureUsage.feature_key==feature.strip().upper())
        rows=db.scalars(stmt.order_by(QFeatureUsage.created_at.desc()).limit(20000)).all()
        by_user=defaultdict(lambda:{"actions":0,"charged":0,"quoted":0,"success":0,"failed":0,"features":defaultdict(int),"last":None})
        allowed_ids=None
        if username.strip():
            q=username.strip().lstrip("@").lower()
            x=db.scalar(select(User).where(func.lower(User.username)==q))
            allowed_ids={x.id} if x else set()
        for r in rows:
            if allowed_ids is not None and r.user_id not in allowed_ids:continue
            if tier.strip() and r.tier_key!=tier.strip().upper():continue
            d=by_user[r.user_id];d["actions"]+=1;d["charged"]+=r.charged_micros;d["quoted"]+=r.quoted_micros
            d["success"]+=int(r.status=="SUCCESS");d["failed"]+=int(r.status!="SUCCESS");d["features"][r.feature_key]+=1
            if not d["last"] or r.created_at>d["last"]:d["last"]=r.created_at
        shadow=db.scalars(select(ShadowMonetisationEvent).where(ShadowMonetisationEvent.created_at>=start)).all()
        costs=defaultdict(lambda:{"cost":0,"simq":0})
        for s in shadow:
            if s.user_id:costs[s.user_id]["cost"]+=s.estimated_cost_microusd;costs[s.user_id]["simq"]+=s.simulated_q_micros
        users=[]
        for uid,d in by_user.items():
            x=db.get(User,uid)
            users.append({"user_id":uid,"username":x.username if x else str(uid),"display_name":x.display_name if x else "",
                "tier":_tier_code(db,uid),"actions":d["actions"],"success":d["success"],"failed":d["failed"],
                "charged_q":round(d["charged"]/Q_MICROS,6),"quoted_q":round(d["quoted"]/Q_MICROS,6),
                "simulated_q":round(costs[uid]["simq"]/Q_MICROS,6),"provider_cost_usd":round(costs[uid]["cost"]/1_000_000,6),
                "avg_actions_per_day":round(d["actions"]/max(1,(now()-start).total_seconds()/86400),2),
                "last_active":d["last"].isoformat() if d["last"] else None,
                "features":dict(sorted(d["features"].items(),key=lambda kv:kv[1],reverse=True))})
        users.sort(key=lambda x:x["actions"],reverse=True)
        counts=sorted([x["actions"] for x in users])
        def pct(p):
            if not counts:return 0
            i=min(len(counts)-1,max(0,math.ceil(p*len(counts))-1));return counts[i]
        feat=defaultdict(int)
        for x in users:
            for k,v in x["features"].items():feat[k]+=v
        return {"period":period,"from":start.isoformat(),"users":users,
                "summary":{"active_users":len(users),"total_actions":sum(x["actions"] for x in users),
                           "avg_actions_per_user":round(sum(counts)/len(counts),2) if counts else 0,
                           "median_actions":statistics_median(counts),"p90":pct(.90),"p95":pct(.95),
                           "provider_cost_usd":round(sum(x["provider_cost_usd"] for x in users),6),
                           "simulated_q":round(sum(x["simulated_q"] for x in users),6),
                           "feature_totals":dict(sorted(feat.items(),key=lambda kv:kv[1],reverse=True))}}

    @router.get("/admin/q-usage/export.csv")
    def export_usage(period:str="30d",u=Depends(admin),db:Session=Depends(get_db)):
        data=q_usage(period=period,u=u,db=db)
        buf=io.StringIO();w=csv.writer(buf)
        w.writerow(["username","display_name","tier","actions","success","failed","charged_q","simulated_q","provider_cost_usd","avg_actions_per_day","last_active","features"])
        for x in data["users"]:
            w.writerow([x["username"],x["display_name"],x["tier"],x["actions"],x["success"],x["failed"],x["charged_q"],x["simulated_q"],x["provider_cost_usd"],x["avg_actions_per_day"],x["last_active"],json.dumps(x["features"])])
        return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="lemmiq-q-usage-{period}.csv"'})

    app.include_router(router)

def statistics_median(values):
    if not values:return 0
    s=sorted(values);n=len(s);m=n//2
    return s[m] if n%2 else round((s[m-1]+s[m])/2,2)
