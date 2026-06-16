from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..db import get_db
from ..models import Expert, Review, User, Payment
from ..auth import current_user
from ..config import settings

router=APIRouter()

@router.get("")
def list_experts(category:Optional[str]=None, db:Session=Depends(get_db)):
    q=db.query(Expert).filter(Expert.application_status=="approved", Expert.available==True)
    if category: q=q.filter(Expert.category==category)
    return [{"id":e.id,"name":e.name,"category":e.category,"bio":e.bio,"years_experience":e.years_experience,"fee":e.fee,"rating":e.rating,"verified":e.verified,"city":e.city,"languages":e.languages,"profile_photo_url":e.profile_photo_url} for e in q.all()]

@router.get("/{eid}")
def get_expert(eid:int, db:Session=Depends(get_db)):
    e=db.query(Expert).get(eid)
    if not e or e.application_status!="approved": raise HTTPException(404,"Not found")
    return {"id":e.id,"name":e.name,"category":e.category,"bio":e.bio,"years_experience":e.years_experience,"fee":e.fee,"rating":e.rating,"verified":e.verified,"city":e.city,"languages":e.languages,"profile_photo_url":e.profile_photo_url,"details_price":settings.DETAILS_UNLOCK_AMOUNT,"details_locked":True}

@router.get("/{eid}/paid-details")
def paid_details(eid:int, u:User=Depends(current_user), db:Session=Depends(get_db)):
    e=db.query(Expert).get(eid)
    if not e or e.application_status!="approved": raise HTTPException(404,"Not found")
    paid=db.query(Payment).filter(
        Payment.user_id==u.id,
        Payment.status=="paid",
        Payment.description.in_([
            f"Details unlock for expert #{eid}",
            f"Details unlock for expertise {e.category}",
        ]),
    ).first()
    if not paid and u.role!="admin" and u.id!=e.user_id:
        raise HTTPException(402, f"Pay INR {settings.DETAILS_UNLOCK_AMOUNT} to unlock feedback and experience for this expertise")
    return {
        "experience": f"{e.years_experience or 0} years of experience in {e.category}.",
        "languages": e.languages,
        "feedback_summary": f"{e.name} has a {e.rating or 0} star rating from recent OnCons consultations.",
    }

@router.get("/{eid}/reviews")
def reviews(eid:int, db:Session=Depends(get_db)):
    rows=db.query(Review,User).join(User,User.id==Review.user_id).filter(Review.expert_id==eid).all()
    return [{"id":r.id,"rating":r.rating,"comment":r.comment,"user_name":u.name,"created_at":r.created_at} for r,u in rows]
