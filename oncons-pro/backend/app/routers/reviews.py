from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Review, User, Expert
from ..auth import current_user
from ..schemas import ReviewIn

router=APIRouter()

@router.post("")
def add(b:ReviewIn, u:User=Depends(current_user), db:Session=Depends(get_db)):
    r=Review(user_id=u.id, expert_id=b.expert_id, rating=b.rating, comment=b.comment)
    db.add(r); db.commit(); db.refresh(r)
    # update expert avg rating
    avg=db.query(Review).filter_by(expert_id=b.expert_id).all()
    e=db.query(Expert).get(b.expert_id); e.rating=sum(x.rating for x in avg)/len(avg); db.commit()
    return {"id":r.id}

@router.get("/recent")
def recent(db:Session=Depends(get_db)):
    rows=db.query(Review,User,Expert).join(User,User.id==Review.user_id).join(Expert,Expert.id==Review.expert_id).order_by(Review.id.desc()).limit(12).all()
    return [{"rating":r.rating,"comment":r.comment,"user_name":u.name,"expert_name":e.name} for r,u,e in rows]
