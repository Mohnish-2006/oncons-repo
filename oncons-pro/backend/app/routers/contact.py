from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import SupportTicket
from ..schemas import ContactIn
router=APIRouter()
@router.post("/contact")
def contact(b:ContactIn, db:Session=Depends(get_db)):
    t=SupportTicket(email=b.email, subject=f"Contact from {b.name}", body=b.message)
    db.add(t); db.commit(); return {"ok":True}
