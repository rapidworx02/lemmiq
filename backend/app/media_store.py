"""Private S3-compatible object storage. Configure R2/S3 on Render; never rely on ephemeral Render disk."""
import os
import uuid
from pathlib import Path
from fastapi import HTTPException

BUCKET = os.getenv("MEDIA_BUCKET", "").strip()
ENDPOINT = os.getenv("MEDIA_ENDPOINT", "").strip()
ACCESS = os.getenv("MEDIA_ACCESS_KEY_ID", "").strip()
SECRET = os.getenv("MEDIA_SECRET_ACCESS_KEY", "").strip()
REGION = os.getenv("MEDIA_REGION", "auto").strip()
# Local file storage is strictly for localhost development, not Render.
LOCAL = os.getenv("LEMMIQ_LOCAL_MEDIA", "false").lower() == "true" and not os.getenv("RENDER")
LOCAL_DIR = Path(__file__).resolve().parents[1] / "media_local"


def configured():
    return bool(BUCKET and ENDPOINT and ACCESS and SECRET) or LOCAL


def client():
    if not configured():
        raise HTTPException(503, "Media storage not configured. Set MEDIA_BUCKET, MEDIA_ENDPOINT and media credentials on Render.")
    if LOCAL:
        return None
    import boto3
    return boto3.client("s3", endpoint_url=ENDPOINT, aws_access_key_id=ACCESS,
                        aws_secret_access_key=SECRET, region_name=REGION)


def store(data:bytes):
    obj_key = "attachments/" + uuid.uuid4().hex
    c = client()
    if LOCAL:
        dest = LOCAL_DIR / obj_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    else:
        c.put_object(Bucket=BUCKET, Key=obj_key, Body=data,
                     ContentType="application/octet-stream", CacheControl="private, no-store")
    return obj_key


def stream(obj_key):
    # The caller MUST check chat membership first. Never give out presigned public URLs.
    c = client()
    if LOCAL:
        f = LOCAL_DIR / obj_key
        if not f.is_file():
            raise HTTPException(404, "Media unavailable")
        def chunks():
            with f.open("rb") as src:
                while part := src.read(65536):
                    yield part
        return chunks()
    try:
        body = c.get_object(Bucket=BUCKET, Key=obj_key)["Body"]
    except Exception:
        raise HTTPException(404, "Media unavailable")
    def chunks():
        try:
            while part := body.read(65536):
                yield part
        finally:
            body.close()
    return chunks()
