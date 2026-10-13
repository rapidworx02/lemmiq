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


def _token_parts(token: str):
    if token.startswith("WEB:"):
        return "WEB", token[4:]
    return "ANDROID", token

def notify(tokens:list[str],sender_name:str,chat_id:int,body:str="New message",unread_count:int=1):
    if not tokens or _app() is None:
        return
    from firebase_admin import messaging
    for stored in tokens:
        platform, token = _token_parts(stored)
        try:
            data={
                "type":"chat",
                "chat_id":str(chat_id),
                "sender_name":sender_name[:60],
                "title":sender_name[:60] or "LEMMIQ",
                "body":(body or "New message")[:180],
                "unread_count":str(max(1,int(unread_count))),
                "url":f"/web/#chat-{chat_id}",
            }
            if platform=="WEB":
                messaging.send(messaging.Message(
                    token=token,
                    data=data,
                    webpush=messaging.WebpushConfig(headers={"Urgency":"high"}),
                ))
            else:
                messaging.send(messaging.Message(
                    token=token,
                    data=data,
                    android=messaging.AndroidConfig(priority="high", ttl=3600),
                ))
        except Exception:
            LOG.warning("FCM send failed for a %s device; check token/credentials", platform.lower())


def notify_data(tokens:list[str], data:dict):
    """High-priority authenticated data notification for groups/calls/web PWA."""
    if not tokens or _app() is None:
        return
    from firebase_admin import messaging
    payload={str(k):str(v)[:500] for k,v in data.items() if v is not None}
    if "title" not in payload:
        if payload.get("type") in {"incoming_call","call"}:
            payload["title"]=payload.get("caller_name") or "Incoming LEMMIQ call"
        elif payload.get("type")=="group":
            payload["title"]=payload.get("group_name") or "LEMMIQ group"
        else:
            payload["title"]="LEMMIQ"
    if "body" not in payload:
        payload["body"]="You have a new LEMMIQ update"
    if "url" not in payload:
        if payload.get("group_id"):
            payload["url"]=f"/web/#group-{payload['group_id']}"
        elif payload.get("chat_id"):
            payload["url"]=f"/web/#chat-{payload['chat_id']}"
        elif payload.get("type") in {"incoming_call","call"}:
            payload["url"]="/web/#calls"
        else:
            payload["url"]="/web/#chats"

    for stored in tokens:
        platform, token = _token_parts(stored)
        try:
            if platform=="WEB":
                messaging.send(messaging.Message(
                    token=token,
                    data=payload,
                    webpush=messaging.WebpushConfig(headers={"Urgency":"high"}),
                ))
            else:
                messaging.send(messaging.Message(
                    token=token,
                    data=payload,
                    android=messaging.AndroidConfig(priority="high", ttl=3600),
                ))
        except Exception:
            LOG.warning("FCM data send failed for a %s device", platform.lower())

