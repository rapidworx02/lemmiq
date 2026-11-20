"""Private S3-compatible object storage. Configure R2/S3 on Render; never rely on ephemeral Render disk."""
import os
import uuid
import hashlib
import io
from functools import lru_cache
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


@lru_cache(maxsize=1)
def client():
    if not configured():
        raise HTTPException(503, "Media storage not configured. Set MEDIA_BUCKET, MEDIA_ENDPOINT and media credentials on Render.")
    if LOCAL:
        return None
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=ENDPOINT, aws_access_key_id=ACCESS,
                        aws_secret_access_key=SECRET, region_name=REGION,
                        config=Config(connect_timeout=6, read_timeout=25,
                                      retries={'mode':'standard','max_attempts':2},
                                      max_pool_connections=20))


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


# LEMMIQ_V21316_PRIVATE_THUMBNAILS: thumbnail cache is private object storage,
# keyed by immutable source key. The caller must authorize chat membership first.
@lru_cache(maxsize=48)
def thumbnail(obj_key: str) -> bytes:
    from PIL import Image, ImageOps, UnidentifiedImageError
    key='thumbnails/v21316/'+hashlib.sha256(obj_key.encode()).hexdigest()+'.webp'
    if LOCAL:
        target=LOCAL_DIR/key
        if target.exists():return target.read_bytes()
    else:
        c=client()
        try:
            result=c.get_object(Bucket=BUCKET,Key=key)
            try:return result['Body'].read()
            finally:result['Body'].close()
        except Exception:
            pass  # Not yet generated; read the original and cache its thumbnail.
    parts=[];total=0
    for part in stream(obj_key):
        total+=len(part)
        if total>24*1024*1024:
            raise HTTPException(413,'Photo too large for thumbnail')
        parts.append(part)
    try:
        Image.MAX_IMAGE_PIXELS=24_000_000
        with Image.open(io.BytesIO(b''.join(parts))) as src:
            if src.width*src.height > 24_000_000:
                raise ValueError('Image dimensions too large')
            src=ImageOps.exif_transpose(src)
            src.thumbnail((448,448),Image.Resampling.LANCZOS)
            data=io.BytesIO()
            src.convert('RGB').save(data,format='WEBP',quality=68,method=4)
            out=data.getvalue()
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError):
        raise HTTPException(415,'Cannot generate a photo thumbnail')
    if LOCAL:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(out)
    else:
        client().put_object(Bucket=BUCKET,Key=key,Body=out,
                            ContentType='image/webp',CacheControl='private, max-age=3600')
    return out
