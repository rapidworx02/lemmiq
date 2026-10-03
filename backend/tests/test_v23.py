import os
os.environ.setdefault("LEMMIQ_JWT_SECRET","test-secret-that-is-long-enough-for-lemmiq-v23")
os.environ.setdefault("DATABASE_URL","sqlite:///./v23_test.db")
os.environ.setdefault("LEMMIQ_LOCAL_MEDIA","true")

from fastapi.testclient import TestClient
from app.main import app

def test_groups_voice_and_call_status():
    with TestClient(app) as c:
        a=c.post("/register",json={"username":"v23alpha","display_name":"Alpha","password":"password123"}).json()
        b=c.post("/register",json={"username":"v23beta","display_name":"Beta","password":"password123"}).json()
        ha={"Authorization":"Bearer "+a["token"]};hb={"Authorization":"Bearer "+b["token"]}
        direct=c.post("/chats/direct",headers=ha,json={"user_id":b["user"]["id"]}).json()
        voice=c.post(f"/v23/chats/{direct['id']}/voice",headers=ha,
            files={"file":("voice.m4a",b"test-audio","audio/mp4")},
            data={"duration_ms":"1500","transcript":"hello from voice"})
        assert voice.status_code==200
        assert voice.json()["attachment"]["kind"]=="VOICE"
        g=c.post("/v23/groups",headers=ha,json={"name":"Crew","member_ids":[b["user"]["id"]]})
        assert g.status_code==200
        gid=g.json()["id"]
        assert c.post(f"/v23/groups/{gid}/messages",headers=hb,json={"text":"hello group"}).status_code==200
        listed=c.get("/v23/groups",headers=ha).json()
        assert listed[0]["unread"]>=1
        assert c.post(f"/v23/groups/{gid}/read",headers=ha).status_code==200
        listed=c.get("/v23/groups",headers=ha).json()
        assert listed[0]["unread"]==0
        assert c.post(f"/v23/groups/{gid}/suggest",headers=ha).status_code==200
        status=c.get("/v23/calls/status",headers=ha)
        assert status.status_code==200
