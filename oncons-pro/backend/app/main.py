from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import time
from pathlib import Path
from .db import Base, engine
from .config import settings
from .routers import auth, experts, bookings, payments, ai, reviews, dashboard, admin, contact, expert_portal, me, rooms, uploads

def _validate_production_settings():
    if settings.ENVIRONMENT.strip().lower() not in {"prod", "production"}:
        return
    problems=[]
    if str(engine.url).startswith("sqlite"):
        problems.append("DATABASE_URL must use PostgreSQL in production")
    if settings.JWT_SECRET in {"", "dev-secret", "change-this-before-production"}:
        problems.append("JWT_SECRET must be a strong production secret")
    if "localhost" in settings.FRONTEND_URL or "127.0.0.1" in settings.FRONTEND_URL:
        problems.append("FRONTEND_URL must be a deployed HTTPS URL")
    if "localhost" in settings.ALLOWED_ORIGINS or "127.0.0.1" in settings.ALLOWED_ORIGINS:
        problems.append("ALLOWED_ORIGINS must not include localhost in production")
    if not settings.FRONTEND_URL.startswith("https://"):
        problems.append("FRONTEND_URL must use HTTPS in production")
    if problems:
        raise RuntimeError("Invalid production configuration: " + "; ".join(problems))

_validate_production_settings()

def _is_production():
    return settings.ENVIRONMENT.strip().lower() in {"prod", "production"}

if not _is_production():
    Base.metadata.create_all(bind=engine)

def _sqlite_migrate():
    if not str(engine.url).startswith("sqlite"):
        return
    statements=[
        "ALTER TABLE experts ADD COLUMN city VARCHAR",
        "ALTER TABLE experts ADD COLUMN languages VARCHAR",
        "ALTER TABLE experts ADD COLUMN profile_photo_url VARCHAR",
        "ALTER TABLE experts ADD COLUMN aadhaar_url VARCHAR",
        "ALTER TABLE experts ADD COLUMN certificate_url VARCHAR",
        "ALTER TABLE experts ADD COLUMN certificate_required BOOLEAN DEFAULT 0",
        "ALTER TABLE experts ADD COLUMN certificate_verified BOOLEAN DEFAULT 0",
        "ALTER TABLE experts ADD COLUMN portfolio_url VARCHAR",
        "ALTER TABLE experts ADD COLUMN application_status VARCHAR DEFAULT 'approved'",
        "ALTER TABLE experts ADD COLUMN aadhaar_verified BOOLEAN DEFAULT 0",
        "ALTER TABLE bookings ADD COLUMN meeting_token VARCHAR",
        "ALTER TABLE bookings ADD COLUMN mode VARCHAR DEFAULT 'video'",
        "ALTER TABLE bookings ADD COLUMN free_minutes INTEGER DEFAULT 2",
        "ALTER TABLE bookings ADD COLUMN rate_per_minute FLOAT DEFAULT 25",
        "ALTER TABLE bookings ADD COLUMN call_started_at DATETIME",
        "ALTER TABLE bookings ADD COLUMN call_ended_at DATETIME",
        "ALTER TABLE bookings ADD COLUMN billable_minutes INTEGER DEFAULT 0",
        "ALTER TABLE bookings ADD COLUMN call_charge_status VARCHAR DEFAULT 'not_started'",
        "ALTER TABLE bookings ADD COLUMN details_unlocked BOOLEAN DEFAULT 0",
        "ALTER TABLE payments ADD COLUMN refunded_amount FLOAT DEFAULT 0",
        "ALTER TABLE payments ADD COLUMN refund_ref VARCHAR",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
        try:
            conn.execute(text("UPDATE experts SET application_status='approved' WHERE application_status IS NULL"))
        except Exception:
            pass

if not _is_production():
    _sqlite_migrate()

app = FastAPI(title="OnCons API")
app.add_middleware(GZipMiddleware, minimum_size=1000)

allowed_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
local_origin_regex=r"^http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):(5500|5600)$"
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_origin_regex=local_origin_regex, allow_credentials=True, allow_methods=["GET","POST","PATCH","PUT","DELETE"], allow_headers=["Authorization","Content-Type"])

_rate_buckets={}
@app.middleware("http")
async def security_and_rate_limit(request:Request, call_next):
    if request.url.path.startswith("/api/"):
        ip=request.client.host if request.client else "unknown"
        now=time.time()
        is_auth=request.url.path.startswith("/api/auth/")
        window=900 if is_auth else 60
        limit=30 if is_auth else 120
        key=(ip, "auth" if is_auth else "api")
        hits=[t for t in _rate_buckets.get(key, []) if now-t<window]
        if len(hits)>=limit:
            return JSONResponse({"detail":"Too many requests. Please try again later."}, status_code=429, headers={"Retry-After":str(window)})
        hits.append(now)
        _rate_buckets[key]=hits
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(self), microphone=(self), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; font-src https://fonts.gstatic.com; img-src 'self' data: https:; media-src 'self' blob:; connect-src 'self' http: https: ws: wss:"
    return response

PREFIX="/api"
app.include_router(auth.router, prefix=PREFIX+"/auth", tags=["auth"])
app.include_router(me.router, prefix=PREFIX, tags=["me"])
app.include_router(experts.router, prefix=PREFIX+"/experts", tags=["experts"])
app.include_router(bookings.router, prefix=PREFIX+"/bookings", tags=["bookings"])
app.include_router(payments.router, prefix=PREFIX+"/payments", tags=["payments"])
app.include_router(ai.router, prefix=PREFIX+"/ai", tags=["ai"])
app.include_router(reviews.router, prefix=PREFIX+"/reviews", tags=["reviews"])
app.include_router(dashboard.router, prefix=PREFIX, tags=["user"])
app.include_router(expert_portal.router, prefix=PREFIX+"/expert", tags=["expert"])
app.include_router(admin.router, prefix=PREFIX+"/admin", tags=["admin"])
app.include_router(contact.router, prefix=PREFIX, tags=["contact"])
app.include_router(rooms.router, prefix=PREFIX, tags=["rooms"])
app.include_router(uploads.router, prefix=PREFIX+"/uploads", tags=["uploads"])

if not _is_production():
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.get("/health")
def health(): return {"ok":True}
