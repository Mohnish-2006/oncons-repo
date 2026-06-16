from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Booking, Expert, User
from ..auth import current_user
from ..schemas import BookingIn
from ..config import settings
import secrets

router=APIRouter()

@router.post("")
def create(b:BookingIn, u:User=Depends(current_user), db:Session=Depends(get_db)):
    e=db.query(Expert).get(b.expert_id)
    if not e or e.application_status!="approved": raise HTTPException(404,"Consultant not available")
    mode=(b.mode or "video").lower()
    if mode not in ("video","audio","chat"):
        raise HTTPException(400,"Mode must be video, audio, or chat")
    bk=Booking(user_id=u.id, expert_id=e.id, scheduled_at=b.scheduled_at, fee=e.fee,
               mode=mode,
               free_minutes=settings.CALL_FREE_MINUTES, rate_per_minute=settings.CALL_RATE_PER_MINUTE,
               status="pending_payment", meeting_token=secrets.token_urlsafe(18))
    db.add(bk)
    db.commit(); db.refresh(bk)
    return {"id":bk.id,"status":bk.status,"amount":bk.fee,"message":"Complete payment to confirm this booking."}
