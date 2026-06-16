from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .db import Base, engine
from .config import settings
from .routers import auth, experts, bookings, payments, ai, reviews, dashboard, admin, contact, expert_portal, me

Base.metadata.create_all(bind=engine)

def _sqlite_migrate():
    if not str(engine.url).startswith("sqlite"):
        return
    statements=[
        "ALTER TABLE experts ADD COLUMN city VARCHAR",
        "ALTER TABLE experts ADD COLUMN languages VARCHAR",
        "ALTER TABLE experts ADD COLUMN profile_photo_url VARCHAR",
        "ALTER TABLE experts ADD COLUMN aadhaar_url VARCHAR",
        "ALTER TABLE experts ADD COLUMN application_status VARCHAR DEFAULT 'approved'",
        "ALTER TABLE experts ADD COLUMN aadhaar_verified BOOLEAN DEFAULT 0",
        "ALTER TABLE bookings ADD COLUMN meeting_token VARCHAR",
        "ALTER TABLE bookings ADD COLUMN free_minutes INTEGER DEFAULT 2",
        "ALTER TABLE bookings ADD COLUMN rate_per_minute FLOAT DEFAULT 25",
        "ALTER TABLE bookings ADD COLUMN call_started_at DATETIME",
        "ALTER TABLE bookings ADD COLUMN call_ended_at DATETIME",
        "ALTER TABLE bookings ADD COLUMN billable_minutes INTEGER DEFAULT 0",
        "ALTER TABLE bookings ADD COLUMN call_charge_status VARCHAR DEFAULT 'not_started'",
        "ALTER TABLE bookings ADD COLUMN details_unlocked BOOLEAN DEFAULT 0",
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

_sqlite_migrate()

app = FastAPI(title="OnCons API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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

@app.get("/health")
def health(): return {"ok":True}
