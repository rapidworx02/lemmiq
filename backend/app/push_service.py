"""Optional FCM push. No Firebase credentials -> normal messenger remains functional."""
import base64
import json
import logging
import os

LOG=logging.getLogger("lemmiq.push")
_firebase=None

def _app():
    global _firebase
    if _firebase is not None:
        return _firebase
    raw=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    encoded=os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "").strip()
    if not raw and not encoded:
        return None
    try:
        if encoded:
            raw=base64.b64decode(encoded).decode("utf-8")
        import firebase_admin
        from firebase_admin import credentials
        _firebase=firebase_admin.get_app() if firebase_admin._apps else firebase_admin.initialize_app(
            credentials.Certificate(json.loads(raw)))
        return _firebase
    except Exception:
        LOG.exception("FCM initialization failed")
        return None


def configured():
    return _app() is not None


def notify(tokens:list[str],sender_name:str,chat_id:int,body:str="New message",unread_count:int=1):
    if not tokens or _app() is None:
        return
    from firebase_admin import messaging
    for token in tokens:
        try:
            messaging.send(messaging.Message(
                token=token,
                data={"type":"chat", "chat_id":str(chat_id), "sender_name":sender_name[:60], "body":(body or "New message")[:180], "unread_count":str(max(1,int(unread_count)))},
                android=messaging.AndroidConfig(priority="high", ttl=3600),
            ))
        except Exception:
            LOG.warning("FCM send failed for a device; check token/credentials")
