from pathlib import Path
import secrets

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth import current_user
from ..config import settings
from ..models import User

router = APIRouter()

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


@router.post("")
async def upload_file(file: UploadFile = File(...), u: User = Depends(current_user)):
    suffix = ALLOWED_TYPES.get(file.content_type or "")
    if not suffix:
        raise HTTPException(400, "Only JPG, PNG, WebP, and PDF files are allowed")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"File must be {settings.MAX_UPLOAD_MB} MB or smaller")
    if settings.CLOUDINARY_URL:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL, secure=True)
            result = cloudinary.uploader.upload(
                data,
                resource_type="auto",
                folder=f"oncons/{u.id}",
                public_id=secrets.token_urlsafe(12),
                overwrite=False,
            )
            return {"url": result["secure_url"], "provider": "cloudinary", "content_type": file.content_type}
        except Exception as exc:
            raise HTTPException(502, "Cloudinary upload failed") from exc

    upload_dir = Path(settings.UPLOAD_DIR) / str(u.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_urlsafe(16)}{suffix}"
    target = upload_dir / name
    target.write_bytes(data)
    return {"url": f"/{settings.UPLOAD_DIR}/{u.id}/{name}", "provider": "local", "content_type": file.content_type}
