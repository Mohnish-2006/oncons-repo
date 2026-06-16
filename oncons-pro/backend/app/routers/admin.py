from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Expert, Booking, Payment, Review, Subscription
from ..auth import require_role

router=APIRouter()
A=Depends(require_role("admin"))

@router.get("/stats")
def stats(_=A, db:Session=Depends(get_db)):
    paid=db.query(Payment).filter_by(status="paid").all()
    bookings=db.query(Booking).filter(Booking.status!="pending_payment").all()
    return {"users":db.query(User).count(),"experts":db.query(Expert).count(),
            "bookings":len(bookings),
            "earnings":sum(p.amount for p in paid),
            "revenue":sum(p.amount for p in paid)}

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
        "description":p.description,
        "created_at":p.created_at,
    }

def _dump(rows, fields):
    return [{f:getattr(r,f) for f in fields} for r in rows]

@router.get("/users")
def users(_=A, db:Session=Depends(get_db)): return _dump(db.query(User).all(), ["id","name","email","role","plan"])
@router.get("/experts")
def experts(_=A, db:Session=Depends(get_db)): return _dump(db.query(Expert).all(), ["id","name","category","fee","rating","verified"])
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
