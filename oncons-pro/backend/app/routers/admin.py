from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from pathlib import Path
from ..db import get_db
from ..db import engine
from ..config import settings
from ..models import User, Expert, Booking, Payment, Review, Subscription, Category, Complaint, Report, SystemSetting, AdminLog, SupportTicket
from ..auth import require_role

router=APIRouter()
A=Depends(require_role("admin"))

def _admin_log(db:Session, admin:User, action:str, meta:dict=None):
    db.add(AdminLog(admin_id=admin.id, action=action, meta=meta or {}))

@router.get("/stats")
def stats(_=A, db:Session=Depends(get_db)):
    paid=db.query(Payment).filter_by(status="paid").all()
    bookings=db.query(Booking).filter(Booking.status!="pending_payment").all()
    return {"users":db.query(User).count(),"experts":db.query(Expert).count(),
            "bookings":len(bookings),
            "earnings":sum(p.amount for p in paid),
            "revenue":sum(p.amount for p in paid),
            "complaints":db.query(Complaint).filter(Complaint.status!="closed").count(),
            "reports":db.query(Report).filter(Report.status!="closed").count()}

@router.get("/analytics")
def analytics(_=A, db:Session=Depends(get_db)):
    since=datetime.utcnow()-timedelta(days=30)
    users=db.query(User).filter(User.created_at>=since).all()
    paid=db.query(Payment).filter(Payment.status=="paid", Payment.created_at>=since).all()
    bookings=db.query(Booking).filter(Booking.created_at>=since, Booking.status!="pending_payment").all()
    by_day={}
    for row in users:
        key=row.created_at.date().isoformat() if row.created_at else "unknown"
        by_day.setdefault(key, {"users":0,"revenue":0,"bookings":0})
        by_day[key]["users"]+=1
    for row in paid:
        key=row.created_at.date().isoformat() if row.created_at else "unknown"
        by_day.setdefault(key, {"users":0,"revenue":0,"bookings":0})
        by_day[key]["revenue"]+=row.amount or 0
    for row in bookings:
        key=row.created_at.date().isoformat() if row.created_at else "unknown"
        by_day.setdefault(key, {"users":0,"revenue":0,"bookings":0})
        by_day[key]["bookings"]+=1
    categories={}
    top={}
    cancellations=0
    for booking in db.query(Booking).filter(Booking.status!="pending_payment").all():
        if booking.status=="cancelled":
            cancellations+=1
        expert=db.query(Expert).get(booking.expert_id)
        if expert:
            categories[expert.category or "General"]=categories.get(expert.category or "General",0)+1
            top[expert.name or f"Expert {expert.id}"]=top.get(expert.name or f"Expert {expert.id}",0)+1
    return {
        "daily": [{"date":k, **v} for k,v in sorted(by_day.items())],
        "totals": {"users":db.query(User).count(),"revenue":sum(p.amount or 0 for p in db.query(Payment).filter_by(status="paid").all()),"bookings":db.query(Booking).filter(Booking.status!="pending_payment").count(),"cancellations":cancellations},
        "popular_categories": sorted([{"category":k,"bookings":v} for k,v in categories.items()], key=lambda x:x["bookings"], reverse=True)[:10],
        "top_consultants": sorted([{"name":k,"bookings":v} for k,v in top.items()], key=lambda x:x["bookings"], reverse=True)[:10],
    }

def _booking_row(b:Booking, db:Session):
    customer=db.query(User).get(b.user_id)
    expert=db.query(Expert).get(b.expert_id)
    expert_user=db.query(User).get(expert.user_id) if expert and expert.user_id else None
    return {
        "id":b.id,
        "customer_name":customer.name if customer else "Unknown user",
        "customer_email":customer.email if customer else "",
        "expert_name":expert.name if expert else "Unknown consultant",
        "expert_email":expert_user.email if expert_user else "",
        "expert_category":expert.category if expert else "",
        "status":b.status,
        "fee":b.fee,
        "scheduled_at":b.scheduled_at,
        "meeting_url":f"/dashboard/booking-room.html?token={b.meeting_token}" if b.meeting_token else "",
    }

def _payment_row(p:Payment, db:Session):
    user=db.query(User).get(p.user_id)
    booking=db.query(Booking).get(p.booking_id) if p.booking_id else None
    expert=db.query(Expert).get(booking.expert_id) if booking else None
    expert_user=db.query(User).get(expert.user_id) if expert and expert.user_id else None
    return {
        "id":p.id,
        "paid_by":user.name if user else "Unknown user",
        "user_email":user.email if user else "",
        "expert_name":expert.name if expert else "",
        "expert_email":expert_user.email if expert_user else "",
        "amount":p.amount,
        "provider":p.provider,
        "status":p.status,
        "refunded_amount":p.refunded_amount or 0,
        "refund_ref":p.refund_ref,
        "description":p.description,
        "created_at":p.created_at,
    }

def _dump(rows, fields):
    return [{f:getattr(r,f) for f in fields} for r in rows]

@router.get("/users")
def users(_=A, db:Session=Depends(get_db)): return _dump(db.query(User).all(), ["id","name","email","role","plan"])
@router.get("/experts")
def experts(_=A, db:Session=Depends(get_db)): return _dump(db.query(Expert).all(), ["id","name","category","fee","rating","verified","certificate_verified","application_status"])
@router.get("/bookings")
def bookings(_=A, db:Session=Depends(get_db)):
    rows=db.query(Booking).filter(Booking.status!="pending_payment").order_by(Booking.scheduled_at.asc()).all()
    return [_booking_row(b, db) for b in rows]
@router.get("/payments")
def payments(_=A, db:Session=Depends(get_db)):
    rows=db.query(Payment).filter_by(status="paid").order_by(Payment.created_at.desc()).all()
    return [_payment_row(p, db) for p in rows]
@router.get("/upcoming-bookings")
def upcoming_bookings(_=A, db:Session=Depends(get_db)):
    from datetime import datetime
    rows=db.query(Booking).filter(Booking.status!="pending_payment", Booking.scheduled_at>=datetime.utcnow()).order_by(Booking.scheduled_at.asc()).limit(8).all()
    return [_booking_row(b, db) for b in rows]
@router.get("/reviews")
def reviews(_=A, db:Session=Depends(get_db)): return _dump(db.query(Review).all(), ["id","user_id","expert_id","rating","comment"])
@router.get("/subscriptions")
def subs(_=A, db:Session=Depends(get_db)): return _dump(db.query(Subscription).all(), ["id","user_id","plan","status","renews_at"])

@router.patch("/experts/{expert_id}/verification")
def verify_expert(expert_id:int, payload:dict, admin:User=A, db:Session=Depends(get_db)):
    expert=db.query(Expert).get(expert_id)
    if not expert:
        raise HTTPException(404,"Consultant not found")
    status=(payload.get("application_status") or expert.application_status or "pending").lower()
    if status not in ("draft","pending","approved","rejected"):
        raise HTTPException(400,"Invalid application status")
    expert.application_status=status
    expert.verified=status=="approved"
    if "certificate_verified" in payload:
        expert.certificate_verified=bool(payload["certificate_verified"])
    if "aadhaar_verified" in payload:
        expert.aadhaar_verified=bool(payload["aadhaar_verified"])
    _admin_log(db, admin, "expert.verification.update", {"expert_id":expert.id,"status":status})
    db.commit()
    return {"ok":True,"status":expert.application_status}

@router.get("/categories")
def categories(_=A, db:Session=Depends(get_db)):
    return _dump(db.query(Category).order_by(Category.name.asc()).all(), ["id","name","icon"])

@router.post("/categories")
def create_category(payload:dict, admin:User=A, db:Session=Depends(get_db)):
    name=(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400,"Category name required")
    existing=db.query(Category).filter_by(name=name).first()
    if existing:
        return {"id":existing.id,"name":existing.name,"icon":existing.icon}
    c=Category(name=name, icon=(payload.get("icon") or "").strip())
    db.add(c)
    _admin_log(db, admin, "category.create", {"name":name})
    db.commit(); db.refresh(c)
    return {"id":c.id,"name":c.name,"icon":c.icon}

@router.get("/complaints")
def complaints(_=A, db:Session=Depends(get_db)):
    return _dump(db.query(Complaint).order_by(Complaint.id.desc()).all(), ["id","user_id","email","subject","priority","status","resolution","created_at"])

@router.patch("/complaints/{complaint_id}")
def update_complaint(complaint_id:int, payload:dict, admin:User=A, db:Session=Depends(get_db)):
    complaint=db.query(Complaint).get(complaint_id)
    if not complaint:
        raise HTTPException(404,"Complaint not found")
    for key in ("priority","status","resolution"):
        if key in payload:
            setattr(complaint,key,payload[key])
    _admin_log(db, admin, "complaint.update", {"complaint_id":complaint.id,"status":complaint.status})
    db.commit()
    return {"ok":True}

@router.get("/reports")
def reports(_=A, db:Session=Depends(get_db)):
    return _dump(db.query(Report).order_by(Report.id.desc()).all(), ["id","reporter_id","target_type","target_id","reason","status","created_at"])

@router.patch("/reports/{report_id}")
def update_report(report_id:int, payload:dict, admin:User=A, db:Session=Depends(get_db)):
    report=db.query(Report).get(report_id)
    if not report:
        raise HTTPException(404,"Report not found")
    status=(payload.get("status") or report.status).lower()
    if status not in ("open","reviewing","closed","dismissed"):
        raise HTTPException(400,"Invalid report status")
    report.status=status
    _admin_log(db, admin, "report.update", {"report_id":report.id,"status":status})
    db.commit()
    return {"ok":True}

@router.get("/support-tickets")
def support_tickets(_=A, db:Session=Depends(get_db)):
    return _dump(db.query(SupportTicket).order_by(SupportTicket.id.desc()).all(), ["id","user_id","email","subject","body","status","created_at"])

@router.get("/audit-logs")
def audit_logs(_=A, db:Session=Depends(get_db)):
    return _dump(db.query(AdminLog).order_by(AdminLog.id.desc()).limit(100).all(), ["id","admin_id","action","meta","created_at"])

@router.get("/settings")
def settings_list(_=A, db:Session=Depends(get_db)):
    return _dump(db.query(SystemSetting).order_by(SystemSetting.key.asc()).all(), ["id","key","value","updated_at"])

@router.put("/settings/{key}")
def upsert_setting(key:str, payload:dict, admin:User=A, db:Session=Depends(get_db)):
    setting=db.query(SystemSetting).filter_by(key=key).first()
    if not setting:
        setting=SystemSetting(key=key)
        db.add(setting)
    setting.value=payload.get("value")
    setting.updated_at=datetime.utcnow()
    _admin_log(db, admin, "setting.upsert", {"key":key})
    db.commit()
    return {"ok":True,"key":setting.key,"value":setting.value}

@router.get("/platform-health")
def platform_health(_=A, db:Session=Depends(get_db)):
    checks={"database":False,"payments":False,"email":False,"storage":False}
    try:
        db.execute(text("SELECT 1"))
        checks["database"]=True
    except Exception:
        checks["database"]=False
    checks["payments"]=bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
    checks["email"]=bool(settings.SMTP_HOST and settings.SMTP_USER and settings.FROM_EMAIL)
    checks["storage"]=bool(settings.CLOUDINARY_URL)
    return {"ok":all(checks.values()),"environment":settings.ENVIRONMENT,"checks":checks}

@router.get("/database-backup")
def database_backup(_=A):
    if not settings.DATABASE_URL.startswith("sqlite"):
        return {"strategy":"managed-postgres","message":"Use Neon/Render managed backups or pg_dump from a secure job."}
    db_path=Path(settings.DATABASE_URL.replace("sqlite:///",""))
    if not db_path.is_absolute():
        db_path=Path.cwd()/db_path
    return {"strategy":"sqlite-file","path":str(db_path),"exists":db_path.exists(),"size_bytes":db_path.stat().st_size if db_path.exists() else 0}
