"""Minimal V1.8 Business Beta smoke test.
Run against a disposable SQLite DB, not production.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./lemmiq_business_test.db")
os.environ.setdefault("LEMMIQ_JWT_SECRET", "development-test-secret-please-change-123456789")

from fastapi.testclient import TestClient
from app.main import app


def run():
    with TestClient(app) as c:
        owner = c.post("/register", json={"username":"bizowner_test","display_name":"Owner","password":"password123"})
        customer = c.post("/register", json={"username":"bizcustomer_test","display_name":"Customer","password":"password123"})
        assert owner.status_code == 200, owner.text
        assert customer.status_code == 200, customer.text
        h = {"Authorization":"Bearer " + owner.json()["token"]}
        hc = {"Authorization":"Bearer " + customer.json()["token"]}
        uid = customer.json()["user"]["id"]
        assert c.put("/business/profile", headers=h, json={
            "enabled":True,"business_name":"Test Business","business_type":"Services","description":"Test services",
            "website":"","phone":"","email":"","hours":"Mon-Fri","service_area":"Sydney","tone":"Friendly",
            "currency":"AUD","auto_threshold":90
        }).status_code == 200
        assert c.post("/business/knowledge", headers=h, json={
            "category":"PRICING","title":"Example service","content":"Example service starts from $100.",
            "source":"Test","approved":True,"active":True
        }).status_code == 200
        chat = c.post("/chats/direct", headers=h, json={"user_id":uid}).json()
        cid = chat["id"]
        assert c.put(f"/business/chats/{cid}", headers=h, json={"enabled":True,"mode":"ASSIST","customer_label":"Lead"}).status_code == 200
        assert c.post(f"/chats/{cid}/messages", headers=hc, json={"text":"How much is the example service?"}).status_code == 200
        answer = c.post(f"/business/chats/{cid}/suggest", headers=h, json={})
        assert answer.status_code == 200, answer.text
        assert answer.json()["reply"]
        print("LEMMIQ V1.8 Business Beta smoke test PASS")


if __name__ == "__main__":
    run()
