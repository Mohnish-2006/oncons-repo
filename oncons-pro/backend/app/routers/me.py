from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Booking, Payment, Subscription, Expert, Notification, Message
from ..notifications import send_email
from ..auth import current_user
from ..schemas import ProfilePatch
from ..config import settings
from datetime import datetime
import math

router=APIRouter()
CALL_PACKAGES={10:49,15:69,30:129}

@router.get("/me")
def me(u:User=Depends(current_user)):
    return {"id":u.id,"name":u.name,"email":u.email,"phone":u.phone,"role":u.role,"plan":u.plan,"avatar_url":u.avatar_url}

@router.patch("/me")
def update_me(b:ProfilePatch, u:User=Depends(current_user), db:Session=Depends(get_db)):
    for k,v in b.dict(exclude_unset=True).items(): setattr(u,k,v)
    db.commit(); return {"ok":True}

@router.get("/me/bookings")
def my_bookings(u:User=Depends(current_user), db:Session=Depends(get_db)):
    rows=db.query(Booking,Expert).join(Expert,Expert.id==Booking.expert_id).filter(Booking.user_id==u.id, Booking.status!="pending_payment").all()
    return [{"id":b.id,"expert_id":e.id,"expert_name":e.name,"expert_category":e.category,
             "scheduled_at":b.scheduled_at,"status":b.status,"fee":b.fee,
             "mode":getattr(b,"mode","video") or "video",
             "meeting_url":f"/dashboard/booking-room.html?token={b.meeting_token}&mode={(getattr(b,'mode','video') or 'video')}"} for b,e in rows]

@router.get("/me/payments")
def my_payments(u:User=Depends(current_user), db:Session=Depends(get_db)):
    return [{"id":p.id,"amount":p.amount,"status":p.status,"description":p.description or "Payment","created_at":p.created_at} for p in db.query(Payment).filter_by(user_id=u.id).all()]

@router.get("/me/subscription")
def my_sub(u:User=Depends(current_user), db:Session=Depends(get_db)):
    s=db.query(Subscription).filter_by(user_id=u.id,status="active").order_by(Subscription.id.desc()).first()
    if not s: from fastapi import HTTPException; raise HTTPException(404,"none")
    return {"plan":s.plan,"status":s.status,"renews_at":s.renews_at}

@router.get("/me/notifications")
def my_notif(u:User=Depends(current_user), db:Session=Depends(get_db)):
    return [{"id":n.id,"title":n.title,"body":n.body,"created_at":n.created_at} for n in db.query(Notification).filter_by(user_id=u.id).order_by(Notification.id.desc()).all()]

def _booking_for_user(db:Session, u:User, token:str):
    q=db.query(Booking,Expert,User).join(Expert,Expert.id==Booking.expert_id).join(User,User.id==Booking.user_id).filter(Booking.meeting_token==token)
    row=q.first()
    if not row: raise HTTPException(404,"Booking not found")
    b,e,customer=row
    if u.id not in (b.user_id, e.user_id) and u.role!="admin":
        raise HTTPException(403,"Not allowed")
    return b,e,customer

@router.get("/me/booking-room/{token}")
def booking_room(token:str, u:User=Depends(current_user), db:Session=Depends(get_db)):
    b,e,customer=_booking_for_user(db,u,token)
    if b.status=="pending_payment":
        raise HTTPException(402,"Complete booking payment to open the consultation room")
    if b.status=="requested":
        raise HTTPException(403,"Waiting for consultant to accept this booking")
    if b.status=="cancelled":
        raise HTTPException(403,"This booking was rejected by the consultant")
    msgs=db.query(Message,User).join(User,User.id==Message.sender_id).filter(Message.booking_id==b.id).order_by(Message.id.asc()).all()
    charge_amount=(b.billable_minutes or 0) * (b.rate_per_minute or 0)
    if b.billable_minutes in CALL_PACKAGES:
        charge_amount=CALL_PACKAGES[b.billable_minutes]
    expert_user=db.query(User).get(e.user_id) if e.user_id else None
    viewer_is_customer=u.id==customer.id
    viewer_is_expert=bool(e.user_id and u.id==e.user_id)
    return {"booking":{"id":b.id,"scheduled_at":b.scheduled_at,"status":b.status,"fee":b.fee,
                       "mode":getattr(b,"mode","video") or "video",
                       "free_minutes":b.free_minutes,"rate_per_minute":b.rate_per_minute,
                       "call_started_at":b.call_started_at,"call_ended_at":b.call_ended_at,
                       "billable_minutes":b.billable_minutes,"call_charge_status":b.call_charge_status,
                       "call_charge_amount":charge_amount,"call_packages":CALL_PACKAGES,
                       "paid_call_minutes":b.billable_minutes if b.call_charge_status=="paid" else 0,
                       "premium_call_free":customer.plan=="premium"},
            "expert":{"id":e.id,"name":e.name,"category":e.category,"email":expert_user.email if expert_user else None,"phone":expert_user.phone if expert_user else None},
            "customer":{"id":customer.id,"name":customer.name,"email":customer.email,"phone":customer.phone},
            "viewer":{"id":u.id,"role":u.role,"is_customer":viewer_is_customer,"is_expert":viewer_is_expert,"call_payment_required":viewer_is_customer},
            "messages":[{"id":m.id,"sender_id":m.sender_id,"sender_name":sender.name,"content":m.content,"created_at":m.created_at} for m,sender in msgs]}

@router.post("/me/booking-room/{token}/call/start")
def start_call(token:str, u:User=Depends(current_user), db:Session=Depends(get_db)):
    b,e,customer=_booking_for_user(db,u,token)
    expert_user=db.query(User).get(e.user_id) if e.user_id else None
    join_path=f"/dashboard/booking-room.html?token={b.meeting_token}"
    if u.id!=customer.id or u.role=="admin":
        b.call_started_at=datetime.utcnow()
        b.call_ended_at=None
        join_link=f"{settings.FRONTEND_URL}{join_path}"
        db.add(Notification(user_id=customer.id, title="Joined the meet", body=f"{e.name} joined the meet."))
        send_email(customer.email, "OnCons meet joined", f"{e.name} joined the meet.\n\nJoin link: {join_link}")
        db.commit()
        return {"started_at":b.call_started_at,"free_minutes":999,"rate_per_minute":0,"host_free":True}
    if expert_user:
        join_link=f"{settings.FRONTEND_URL}{join_path}"
        db.add(Notification(user_id=expert_user.id, title="Joined the meet", body=f"{customer.name} joined the meet."))
        send_email(expert_user.email, "OnCons meet joined", f"{customer.name} joined the meet.\n\nJoin link: {join_link}")
    if customer.plan=="premium":
        b.call_started_at=datetime.utcnow()
        b.call_ended_at=None
        b.billable_minutes=0
        b.call_charge_status="paid"
        db.commit()
        return {"started_at":b.call_started_at,"free_minutes":999,"rate_per_minute":0,"premium_call_free":True}
    if b.call_charge_status=="payment_due":
        raise HTTPException(402,"Pay the call charge to continue the call")
    if b.call_charge_status=="paid":
        b.call_started_at=datetime.utcnow()
        b.call_ended_at=None
        db.commit()
        return {"started_at":b.call_started_at,"free_minutes":b.billable_minutes or 20,"rate_per_minute":0,"paid_package":True}
    if b.call_charge_status in ("paid","not_started") or not b.call_started_at:
        b.call_started_at=datetime.utcnow()
        b.call_ended_at=None
        b.billable_minutes=0
        b.call_charge_status="free"
        db.commit()
    return {"started_at":b.call_started_at,"free_minutes":b.free_minutes,"rate_per_minute":b.rate_per_minute}

@router.post("/me/booking-room/{token}/call/end")
def end_call(token:str, payload:dict=None, u:User=Depends(current_user), db:Session=Depends(get_db)):
    b,e,customer=_booking_for_user(db,u,token)
    force_charge=bool(payload.get("force_charge")) if isinstance(payload, dict) else False
    if not b.call_started_at and force_charge:
        raise HTTPException(400,"Call has not started")
    if not b.call_started_at:
        b.call_started_at=datetime.utcnow()
    b.call_ended_at=datetime.utcnow()
    if u.id!=customer.id or u.role=="admin":
        b.status="completed"
        db.add(Notification(user_id=customer.id, title="Consultation completed", body="Consultation completed."))
        if e.user_id:
            db.add(Notification(user_id=e.user_id, title="Consultation completed", body="Consultation completed."))
        db.commit()
        return {"total_minutes":0,"free_minutes":999,"billable_minutes":0,
                "rate_per_minute":0,"amount":0,"status":b.call_charge_status,
                "host_free":True,"booking_status":b.status}
    if b.call_charge_status=="paid":
        if force_charge:
            b.call_charge_status="payment_due"
            db.commit()
            return {"total_minutes":b.billable_minutes or 0,"free_minutes":0,"billable_minutes":b.billable_minutes or 10,
                    "rate_per_minute":0,"amount":0,"status":b.call_charge_status,
                    "paid_package_expired":True}
        b.status="completed"
        if e.user_id:
            db.add(Notification(user_id=e.user_id, title="Consultation completed", body="Consultation completed."))
        db.add(Notification(user_id=customer.id, title="Consultation completed", body="Consultation completed. Please submit feedback."))
        db.commit()
        return {"total_minutes":b.billable_minutes or 0,"free_minutes":b.billable_minutes or 0,"billable_minutes":0,
                "rate_per_minute":0,"amount":0,"status":b.call_charge_status,
                "paid_package":True,"booking_status":b.status,"needs_feedback":True,"expert_id":e.id}
    if not force_charge:
        b.status="completed"
        if e.user_id:
            db.add(Notification(user_id=e.user_id, title="Consultation completed", body="Consultation completed."))
        db.add(Notification(user_id=customer.id, title="Consultation completed", body="Consultation completed. Please submit feedback."))
        db.commit()
        return {"total_minutes":0,"free_minutes":b.free_minutes,"billable_minutes":0,
                "rate_per_minute":0,"amount":0,"status":b.call_charge_status,
                "booking_status":b.status,"needs_feedback":True,"expert_id":e.id}
    if customer.plan=="premium":
        b.billable_minutes=0
        b.call_charge_status="paid"
        db.commit()
        return {"total_minutes":0,"free_minutes":999,"billable_minutes":0,
                "rate_per_minute":0,"amount":0,"status":b.call_charge_status,
                "premium_call_free":True}
    total_seconds=max(0, (b.call_ended_at-b.call_started_at).total_seconds())
    total_minutes=max(1, math.ceil(total_seconds/60))
    force_charge=bool(payload.get("force_charge")) if isinstance(payload, dict) else False
    b.billable_minutes=max(0, total_minutes-(b.free_minutes or 0))
    if force_charge and b.billable_minutes == 0:
        b.billable_minutes=1
    if b.billable_minutes:
        b.call_charge_status="payment_due"
    else:
        b.call_charge_status="free"
    db.commit()
    return {"total_minutes":total_minutes,"free_minutes":b.free_minutes,"billable_minutes":b.billable_minutes,
            "rate_per_minute":b.rate_per_minute,"amount":b.billable_minutes*(b.rate_per_minute or 0),
            "status":b.call_charge_status}

@router.post("/me/booking-room/{token}/messages")
def send_booking_message(token:str, payload:dict, u:User=Depends(current_user), db:Session=Depends(get_db)):
    b,e,customer=_booking_for_user(db,u,token)
    content=(payload.get("content") or "").strip()
    if not content: raise HTTPException(400,"Message required")
    msg=Message(booking_id=b.id, sender_id=u.id, content=content[:2000])
    db.add(msg); db.commit(); db.refresh(msg)
    return {"id":msg.id,"sender_id":u.id,"sender_name":u.name,"content":msg.content,"created_at":msg.created_at}
