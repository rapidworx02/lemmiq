"""V1.7 REST smoke tests using isolated SQLite and local test-only storage."""
import os
import tempfile
import pathlib

# Configure before importing server, which creates its SQLAlchemy engine at module import.
TEMP=pathlib.Path(tempfile.mkdtemp(prefix="lemmiq-v17-"))
os.environ["DATABASE_URL"]="sqlite:///"+str(TEMP/"test.db")
os.environ["LEMMIQ_JWT_SECRET"]="v17-tests-superlong-random-secret-for-private-beta"
os.environ["LEMMIQ_LOCAL_MEDIA"]="true"
os.environ.pop("ANTHROPIC_API_KEY",None)
os.environ.pop("FIREBASE_SERVICE_ACCOUNT_JSON",None)
os.environ.pop("FIREBASE_SERVICE_ACCOUNT_B64",None)

from fastapi.testclient import TestClient
from app.main import app


def test_v17_media_contact_permissions_and_push_registration():
    with TestClient(app) as client:
        assert client.get("/health").json()["version"]=="2.4.1"
        a=client.post("/register",json={"username":"tester_one","display_name":"One","password":"password123"})
        b=client.post("/register",json={"username":"tester_two","display_name":"Two","password":"password123"})
        assert a.status_code==200 and b.status_code==200,(a.text,b.text)
        ha={"Authorization":"Bearer "+a.json()["token"]}
        hb={"Authorization":"Bearer "+b.json()["token"]}
        chat=client.post("/chats/direct",headers=ha,json={"user_id":b.json()["user"]["id"]}).json()
        cid=chat["id"]
        img=b"\x89PNG\r\n\x1a\n"+b"file-test-not-a-real-png"
        upload=client.post(f"/chats/{cid}/attachments",headers=ha,
            files={"file":("photo.png",img,"image/png")})
        assert upload.status_code==200,upload.text
        mid=upload.json()["attachment"]["media_id"]
        assert upload.json()["attachment"]["kind"]=="PHOTO"
        assert client.get(f"/media/{mid}",headers=ha).content==img
        assert client.get(f"/media/{mid}",headers=hb).content==img
        stranger=client.post("/register",json={"username":"tester_three","display_name":"Three","password":"password123"})
        hc={"Authorization":"Bearer "+stranger.json()["token"]}
        assert client.get(f"/media/{mid}",headers=hc).status_code==404
        assert client.get(f"/media/{mid}").status_code==401
        assert client.post(f"/chats/{cid}/attachments",headers=ha,
            files={"file":("bad.jpg",b"not-a-photo","image/jpeg")}).status_code==415
        assert client.post(f"/chats/{cid}/attachments",headers=ha,
            files={"file":("huge.txt",b"a"*(20*1024*1024+1),"text/plain")}).status_code==413
        contact=client.post(f"/chats/{cid}/contacts",headers=ha,
            json={"display_name":"Sample Contact","phone":"+61 400 000 000"})
        assert contact.status_code==200,contact.text
        assert contact.json()["attachment"]["contact_name"]=="Sample Contact"
        assert client.post(f"/chats/{cid}/contacts",headers=ha,
            json={"display_name":"Bad","phone":"invalid"}).status_code==422
        msgs=client.get(f"/chats/{cid}/messages",headers=hb).json()
        assert len(msgs)==2 and msgs[0]["attachment"]["media_id"]==mid
        token="fcm-token-"+"x"*70
        assert client.post("/push/register",headers=ha,json={"token":token}).status_code==200
        assert client.request("DELETE","/push/unregister",headers=ha,json={"token":token}).status_code==200
        suggestion=client.post("/external/suggest",headers=ha,json={
            "source":"WhatsApp","contact":"Sam","messages":[
                {"source":"WhatsApp","contact":"Sam","text":"Hi!"}]})
        assert suggestion.status_code==200,suggestion.text
        assert suggestion.json()["reply"]
        agent=client.post("/agent/ask",headers=ha,json={"question":"What did Sam say?",
            "external_context":[{"source":"WhatsApp","contact":"Sam","text":"Hi!"}]})
        assert agent.status_code==200,agent.text
