from __future__ import annotations

import csv
import io
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .admin_rbac import require_admin_access
from .models import BusinessChatSetting, ChatSetting, User
from .v28 import QAdminRole, Q_MICROS
from .v2105_q_features import FEATURES, QFeatureUsage, TIERS, _tier_code
from .v29 import ShadowMonetisationEvent

SHADOW_TO_FEATURE = {
    "Q_AGENT":"Q_CHAT","Q_VISION":"Q_VISION","TRUST":"TRUST_CHECK",
    "CHAT_SUMMARY":"CHAT_SUMMARY","Q_TO_Q":"Q_TO_Q","BUSINESS_AGENT":"BUSINESS_AGENT",
    "SUGGEST_REPLY":"SUGGEST_REPLY","AUTO_MESSAGE":"AUTO_MESSAGE",
}

def utcnow(): return datetime.now(timezone.utc)

def _aware(v):
    if v is None:return None
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)

def _bounds(period,start="",end=""):
    now=utcnow();p=(period or "30d").lower()
    if p=="today": return datetime.combine(now.date(),time.min,tzinfo=timezone.utc),now
    if p=="7d": return now-timedelta(days=7),now
    if p=="30d": return now-timedelta(days=30),now
    if p=="90d": return now-timedelta(days=90),now
    if p in {"year","365d"}: return now-timedelta(days=365),now
    if p=="custom":
        try:sdate=date.fromisoformat(start);edate=date.fromisoformat(end)
        except Exception as exc: raise HTTPException(422,"Custom period requires valid start and end dates") from exc
        if edate<sdate: raise HTTPException(422,"End date must be on or after start date")
        if (edate-sdate).days>730: raise HTTPException(422,"Custom range is limited to 730 days")
        begin=datetime.combine(sdate,time.min,tzinfo=timezone.utc)
        finish=datetime.combine(edate+timedelta(days=1),time.min,tzinfo=timezone.utc)
        return begin,min(finish,now)
    raise HTTPException(422,"Use today, 7d, 30d, 90d, year or custom")

def _pct(values,fraction):
    if not values:return 0.0
    vals=sorted(values);idx=max(0,min(len(vals)-1,math.ceil(len(vals)*fraction)-1))
    return float(vals[idx])

def _median(values):
    if not values:return 0.0
    vals=sorted(values);n=len(vals);m=n//2
    return float(vals[m]) if n%2 else float((vals[m-1]+vals[m])/2)

def _r(v,p=4): return round(float(v or 0),p)

def register_v21072_q_usage(app,current_user,get_db):
    router=APIRouter(prefix="/v21072",tags=["LEMMIQ V2.10.7.2 Q Usage Analytics"])

    def require_usage_read(u:User=Depends(current_user),db:Session=Depends(get_db)):
        role=db.get(QAdminRole,u.id)
        if not role or not role.active: raise HTTPException(403,"Admin access required")
        require_admin_access(db,u.id,role.role,"Q_USAGE","READ")
        return u

    def empty_summary():
        return {"active_users":0,"total_actions":0,"charged_q":0,"simulated_q":0,"provider_cost_usd":0,
                "provider_cost_per_active_user_usd":0,"avg_actions_per_user":0,"p50_actions":0,"p90_actions":0,
                "p95_actions":0,"p50_simulated_q":0,"p90_simulated_q":0,"p95_simulated_q":0,"p95_provider_cost_usd":0}

    def build(db,period="30d",username="",tier="",feature="",start="",end="",limit=200):
        begin,finish=_bounds(period,start,end);limit=max(1,min(int(limit or 200),500))
        uid_filter=None
        if username.strip():
            uname=username.strip().lstrip("@").lower()
            user=db.scalar(select(User).where(func.lower(User.username)==uname))
            if not user:
                return {"period":period,"from":begin.isoformat(),"to":finish.isoformat(),"summary":empty_summary(),
                        "features":[],"tiers":[],"users":[],"catalog":[{"feature_key":k,"feature_name":v} for k,v in FEATURES.items()],
                        "tier_catalog":TIERS,"privacy":"Usage metadata/counts only. No private chat text, prompts, images or raw feature metadata."}
            uid_filter=user.id
        tier_key=tier.strip().upper()
        if tier_key and tier_key not in TIERS: raise HTTPException(422,"Unknown tier")
        feature_key=feature.strip().upper()
        if feature_key and feature_key not in FEATURES: raise HTTPException(422,"Unknown feature key")

        stmt=select(QFeatureUsage).where(QFeatureUsage.created_at>=begin,QFeatureUsage.created_at<finish)
        if uid_filter is not None: stmt=stmt.where(QFeatureUsage.user_id==uid_filter)
        if tier_key: stmt=stmt.where(QFeatureUsage.tier_key==tier_key)
        if feature_key: stmt=stmt.where(QFeatureUsage.feature_key==feature_key)
        usage_rows=db.scalars(stmt).all()

        sstmt=select(ShadowMonetisationEvent).where(ShadowMonetisationEvent.created_at>=begin,ShadowMonetisationEvent.created_at<finish)
        if uid_filter is not None:sstmt=sstmt.where(ShadowMonetisationEvent.user_id==uid_filter)
        shadow_rows=db.scalars(sstmt).all()
        if feature_key: shadow_rows=[x for x in shadow_rows if SHADOW_TO_FEATURE.get((x.feature or "").upper(),(x.feature or "").upper())==feature_key]
        if tier_key:
            allowed={x.user_id for x in usage_rows};shadow_rows=[x for x in shadow_rows if x.user_id in allowed]

        user_ids={x.user_id for x in usage_rows}|{x.user_id for x in shadow_rows if x.user_id}
        if uid_filter is not None:user_ids.add(uid_filter)
        users={u.id:u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

        personal_auto={int(uid):int(c or 0) for uid,c in db.execute(
            select(ChatSetting.user_id,func.count()).where(ChatSetting.user_id.in_(user_ids),ChatSetting.ai_mode=="AUTO").group_by(ChatSetting.user_id)
        )} if user_ids else {}
        business_auto={int(uid):int(c or 0) for uid,c in db.execute(
            select(BusinessChatSetting.user_id,func.count()).where(BusinessChatSetting.user_id.in_(user_ids),BusinessChatSetting.enabled.is_(True),BusinessChatSetting.mode=="AUTO").group_by(BusinessChatSetting.user_id)
        )} if user_ids else {}

        per=defaultdict(lambda:{"features":defaultdict(lambda:{"usage":0,"success":0,"failed":0,"charged":0.0,"quoted":0.0,"shadow":0,"shadow_success":0,"cost":0.0,"sim":0.0}),"first":None,"last":None})
        for row in usage_rows:
            d=per[row.user_id];f=d["features"][row.feature_key];f["usage"]+=1
            if (row.status or "").upper()=="SUCCESS":f["success"]+=1
            else:f["failed"]+=1
            f["charged"]+=row.charged_micros/Q_MICROS;f["quoted"]+=row.quoted_micros/Q_MICROS
            c=_aware(row.created_at)
            if c:d["first"]=c if d["first"] is None or c<d["first"] else d["first"];d["last"]=c if d["last"] is None or c>d["last"] else d["last"]
        for row in shadow_rows:
            if not row.user_id:continue
            key=SHADOW_TO_FEATURE.get((row.feature or "").upper(),(row.feature or "OTHER").upper())
            d=per[row.user_id];f=d["features"][key];f["shadow"]+=1;f["shadow_success"]+=1 if row.success else 0
            f["cost"]+=row.estimated_cost_microusd/1_000_000;f["sim"]+=row.simulated_q_micros/Q_MICROS
            c=_aware(row.created_at)
            if c:d["first"]=c if d["first"] is None or c<d["first"] else d["first"];d["last"]=c if d["last"] is None or c>d["last"] else d["last"]

        ft=defaultdict(lambda:{"actions":0,"success":0,"failed":0,"charged_q":0.0,"provider_cost_usd":0.0,"simulated_q":0.0})
        tt=defaultdict(lambda:{"users":0,"actions":0,"charged_q":0.0,"provider_cost_usd":0.0,"simulated_q":0.0})
        items=[];days=max(1.0,(finish-begin).total_seconds()/86400)
        for uid,d in per.items():
            current_tier=_tier_code(db,uid)
            features=[];actions=success=failed=0;charged=cost=sim=0.0
            for key,f in d["features"].items():
                count=max(int(f["usage"]),int(f["shadow"]))
                succ=int(f["success"]) if f["usage"] else int(f["shadow_success"])
                fail=int(f["failed"]) if f["usage"] else max(0,count-succ)
                if not count and not f["cost"] and not f["sim"]:continue
                one={"feature_key":key,"feature_name":FEATURES.get(key,key.replace("_"," ").title()),"actions":count,"success":succ,"failed":fail,
                     "charged_q":_r(f["charged"],6),"configured_or_quoted_q":_r(f["quoted"],6),"simulated_q":_r(f["sim"],6),"provider_cost_usd":_r(f["cost"],6)}
                features.append(one);actions+=count;success+=succ;failed+=fail;charged+=one["charged_q"];cost+=one["provider_cost_usd"];sim+=one["simulated_q"]
                z=ft[key];z["actions"]+=count;z["success"]+=succ;z["failed"]+=fail;z["charged_q"]+=one["charged_q"];z["provider_cost_usd"]+=one["provider_cost_usd"];z["simulated_q"]+=one["simulated_q"]
            if feature_key and not any(x["feature_key"]==feature_key for x in features):continue
            user=users.get(uid);features.sort(key=lambda x:(-x["actions"],-x["provider_cost_usd"],x["feature_key"]))
            item={"user_id":uid,"username":user.username if user else str(uid),"display_name":user.display_name if user else "","current_tier":current_tier,
                  "actions":actions,"success":success,"failed":failed,"charged_q":_r(charged,6),"simulated_q":_r(sim,6),"provider_cost_usd":_r(cost,6),
                  "avg_actions_per_day":_r(actions/days,2),"first_activity":d["first"].isoformat() if d["first"] else None,"last_activity":d["last"].isoformat() if d["last"] else None,
                  "personal_auto_chats":personal_auto.get(uid,0),"business_auto_chats":business_auto.get(uid,0),"features":features}
            items.append(item);z=tt[current_tier];z["users"]+=1;z["actions"]+=actions;z["charged_q"]+=charged;z["provider_cost_usd"]+=cost;z["simulated_q"]+=sim

        items.sort(key=lambda x:(-x["actions"],-x["provider_cost_usd"],x["username"]));items=items[:limit]
        av=[float(x["actions"]) for x in items];sv=[float(x["simulated_q"]) for x in items];cv=[float(x["provider_cost_usd"]) for x in items]
        active=len(items);total_actions=int(sum(av));total_cost=sum(cv);total_sim=sum(sv)
        summary={"active_users":active,"total_actions":total_actions,"charged_q":_r(sum(x["charged_q"] for x in items),6),"simulated_q":_r(total_sim,6),
                 "provider_cost_usd":_r(total_cost,6),"provider_cost_per_active_user_usd":_r(total_cost/active if active else 0,6),
                 "avg_actions_per_user":_r(total_actions/active if active else 0,2),"p50_actions":_r(_median(av),2),"p90_actions":_r(_pct(av,.90),2),
                 "p95_actions":_r(_pct(av,.95),2),"p50_simulated_q":_r(_median(sv),4),"p90_simulated_q":_r(_pct(sv,.90),4),
                 "p95_simulated_q":_r(_pct(sv,.95),4),"p95_provider_cost_usd":_r(_pct(cv,.95),6)}
        features=[{"feature_key":k,"feature_name":FEATURES.get(k,k.replace("_"," ").title()),"actions":int(v["actions"]),"success":int(v["success"]),
                   "failed":int(v["failed"]),"charged_q":_r(v["charged_q"],6),"simulated_q":_r(v["simulated_q"],6),"provider_cost_usd":_r(v["provider_cost_usd"],6)} for k,v in ft.items()]
        features.sort(key=lambda x:(-x["actions"],-x["provider_cost_usd"],x["feature_key"]))
        tiers=[{"tier_key":k,"users":int(v["users"]),"actions":int(v["actions"]),"avg_actions_per_user":_r(v["actions"]/v["users"] if v["users"] else 0,2),
                "charged_q":_r(v["charged_q"],6),"simulated_q":_r(v["simulated_q"],6),"provider_cost_usd":_r(v["provider_cost_usd"],6),
                "provider_cost_per_user_usd":_r(v["provider_cost_usd"]/v["users"] if v["users"] else 0,6)} for k,v in tt.items()]
        tiers.sort(key=lambda x:TIERS.index(x["tier_key"]) if x["tier_key"] in TIERS else 999)
        return {"period":period,"from":begin.isoformat(),"to":finish.isoformat(),"summary":summary,"features":features,"tiers":tiers,"users":items,
                "catalog":[{"feature_key":k,"feature_name":v} for k,v in FEATURES.items()],"tier_catalog":TIERS,
                "privacy":"Usage metadata/counts only. No private chat text, prompts, images or raw feature metadata."}

    @router.get("/admin/q-usage")
    def q_usage(period:str="30d",username:str="",tier:str="",feature:str="",start:str="",end:str="",limit:int=200,_u:User=Depends(require_usage_read),db:Session=Depends(get_db)):
        return build(db,period,username,tier,feature,start,end,limit)

    @router.get("/admin/q-usage/export.csv")
    def q_usage_csv(period:str="30d",username:str="",tier:str="",feature:str="",start:str="",end:str="",_u:User=Depends(require_usage_read),db:Session=Depends(get_db)):
        data=build(db,period,username,tier,feature,start,end,500);buf=io.StringIO();w=csv.writer(buf)
        w.writerow(["username","display_name","current_tier","actions","success","failed","charged_q","simulated_q","provider_cost_usd","avg_actions_per_day","personal_auto_chats","business_auto_chats","last_activity","feature_breakdown"])
        for x in data["users"]:
            w.writerow([x["username"],x["display_name"],x["current_tier"],x["actions"],x["success"],x["failed"],x["charged_q"],x["simulated_q"],x["provider_cost_usd"],x["avg_actions_per_day"],x["personal_auto_chats"],x["business_auto_chats"],x["last_activity"],json.dumps(x["features"],ensure_ascii=False)])
        return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="lemmiq-q-usage-{period}.csv"'})

    app.include_router(router)
