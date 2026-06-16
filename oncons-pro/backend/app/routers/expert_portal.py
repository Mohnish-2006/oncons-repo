from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Expert, Booking, User, Availability, Payment, Notification, Review
from ..auth import current_user, require_role

router=APIRouter()

def _me(u:User, db:Session)->Expert:
    e=db.query(Expert).filter_by(user_id=u.id).first()
    if not e: raise HTTPException(404,"Expert profile not found")
    return e

@router.get("/me")
def me(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    return {"id":e.id,"name":e.name,"email":u.email,"phone":u.phone,"avatar_url":u.avatar_url,
            "category":e.category,"bio":e.bio,"years_experience":e.years_experience,"fee":e.fee,
            "rating":e.rating,"city":e.city,"languages":e.languages,"profile_photo_url":e.profile_photo_url,
            "certificate_url":e.certificate_url,"certificate_required":e.certificate_required,
            "certificate_verified":e.certificate_verified,"portfolio_url":e.portfolio_url,"verified":e.verified}

@router.patch("/me")
def update_me(payload:dict, u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    for k in ("name","category","bio","years_experience","fee","city","languages","profile_photo_url","portfolio_url"):
        if k in payload: setattr(e,k,payload[k])
    for k in ("name","phone","avatar_url"):
        if k in payload: setattr(u,k,payload[k])
    db.commit(); return {"ok":True}

@router.get("/summary")
def summary(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    bks=db.query(Booking).filter_by(expert_id=e.id).all()
    earnings=sum(b.fee for b in bks if b.status in ("confirmed","completed"))
    upcoming=sum(1 for b in bks if b.status in ("requested","confirmed"))
    return {"bookings":len(bks),"upcoming":upcoming,"earnings":earnings,"rating":e.rating}

@router.get("/bookings")
def bookings(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    rows=db.query(Booking,User).join(User,User.id==Booking.user_id).filter(Booking.expert_id==e.id).all()
    return [{"id":b.id,"user_name":us.name,"scheduled_at":b.scheduled_at,"status":b.status,"fee":b.fee,
             "mode":getattr(b,"mode","video") or "video",
             "meeting_url":f"/dashboard/booking-room.html?token={b.meeting_token}&mode={(getattr(b,'mode','video') or 'video')}"} for b,us in rows]

@router.get("/reviews")
def expert_reviews(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    rows=db.query(Review,User).join(User,User.id==Review.user_id).filter(Review.expert_id==e.id).order_by(Review.id.desc()).all()
    return [{"id":r.id,"rating":r.rating,"comment":r.comment,"user_name":customer.name,"created_at":r.created_at} for r,customer in rows]

@router.post("/bookings/{booking_id}/decision")
def booking_decision(booking_id:int, payload:dict, u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    b=db.query(Booking).filter_by(id=booking_id, expert_id=e.id).first()
    if not b: raise HTTPException(404,"Booking not found")
    decision=(payload.get("decision") or "").lower()
    customer=db.query(User).get(b.user_id)
    if decision=="accept":
        b.status="confirmed"
        if customer:
            db.add(Notification(user_id=customer.id, title="Booking accepted", body=f"{e.name} accepted your booking."))
    elif decision=="reject":
        b.status="cancelled"
        if customer:
            db.add(Notification(user_id=customer.id, title="Booking rejected", body=f"{e.name} rejected this booking. The amount paid will be refunded within 24 hrs."))
    else:
        raise HTTPException(400,"Decision must be accept or reject")
    db.commit()
    return {"ok":True,"status":b.status}

@router.get("/availability")
def get_avail(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    a=db.query(Availability).filter_by(expert_id=e.id).first()
    return {"days":a.days,"from_time":a.from_time,"to_time":a.to_time} if a else {}

@router.put("/availability")
def set_avail(payload:dict, u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    a=db.query(Availability).filter_by(expert_id=e.id).first()
    if not a: a=Availability(expert_id=e.id); db.add(a)
    for k in ("days","from_time","to_time"):
        if k in payload: setattr(a,k,payload[k])
    db.commit(); return {"ok":True}
