from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Expert, Booking, User, Availability, Payment
from ..auth import current_user, require_role

router=APIRouter()

def _me(u:User, db:Session)->Expert:
    e=db.query(Expert).filter_by(user_id=u.id).first()
    if not e: raise HTTPException(404,"Expert profile not found")
    return e

@router.get("/me")
def me(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    return {"id":e.id,"name":e.name,"category":e.category,"bio":e.bio,"years_experience":e.years_experience,"fee":e.fee,"rating":e.rating}

@router.patch("/me")
def update_me(payload:dict, u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    for k in ("name","category","bio","years_experience","fee"):
        if k in payload: setattr(e,k,payload[k])
    db.commit(); return {"ok":True}

@router.get("/summary")
def summary(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    bks=db.query(Booking).filter_by(expert_id=e.id).all()
    earnings=sum(b.fee for b in bks if b.status=="completed")
    return {"bookings":len(bks),"earnings":earnings,"rating":e.rating}

@router.get("/bookings")
def bookings(u:User=Depends(require_role("expert")), db:Session=Depends(get_db)):
    e=_me(u,db)
    rows=db.query(Booking,User).join(User,User.id==Booking.user_id).filter(Booking.expert_id==e.id).all()
    return [{"id":b.id,"user_name":us.name,"scheduled_at":b.scheduled_at,"status":b.status,"fee":b.fee,
             "meeting_url":f"/dashboard/booking-room.html?token={b.meeting_token}"} for b,us in rows]

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
