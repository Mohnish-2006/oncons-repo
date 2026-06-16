from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Expert
from ..models import OTPVerification
from ..schemas import Register, Login, TokenOut, ConsultantRegister, OTPSendIn
from ..auth import hash_pw, verify_pw, make_token
import httpx
from ..config import settings
from datetime import datetime, timedelta
import random

router = APIRouter()

def _user_dict(u:User): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"plan":u.plan}

@router.post("/register", response_model=TokenOut)
def register(b:Register, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=b.email).first(): raise HTTPException(400,"Email already registered")
    u=User(name=b.name,email=b.email,password_hash=hash_pw(b.password),role=b.role if b.role in("user","expert") else "user")
    db.add(u); db.flush()
    if u.role=="expert":
        db.add(Expert(user_id=u.id, name=u.name, category="General"))
    db.commit(); db.refresh(u)
    return {"access_token":make_token(u.id,u.role),"user":_user_dict(u)}

@router.post("/otp/send")
def send_otp(b:OTPSendIn, db:Session=Depends(get_db)):
    code=f"{random.randint(100000,999999)}"
    otp=OTPVerification(email=b.email, phone=b.phone, purpose=b.purpose, code=code,
                        expires_at=datetime.utcnow()+timedelta(minutes=10))
    db.add(otp); db.commit()
    # In production, send this through SMS/email. During local development it is returned for easy testing.
    return {"ok":True, "dev_otp":code, "message":"OTP generated. Connect SMS/email provider before production."}

@router.post("/consultant/register", response_model=TokenOut)
def consultant_register(b:ConsultantRegister, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=b.email).first():
        raise HTTPException(400,"Email already registered")
    otp=db.query(OTPVerification).filter_by(email=b.email, purpose="consultant_registration", code=b.otp).order_by(OTPVerification.id.desc()).first()
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400,"Invalid or expired OTP")
    otp.verified=True
    u=User(name=b.name,email=b.email,phone=b.phone,password_hash=hash_pw(b.password),role="expert")
    db.add(u); db.flush()
    e=Expert(user_id=u.id, name=b.name, category=b.category, bio=b.bio,
             years_experience=b.years_experience, fee=b.fee, city=b.city,
             languages=b.languages, profile_photo_url=b.profile_photo_url,
             aadhaar_url=b.aadhaar_url, verified=False, available=True,
             application_status="approved", aadhaar_verified=False)
    db.add(e); db.commit(); db.refresh(u)
    return {"access_token":make_token(u.id,u.role),"user":_user_dict(u)}

@router.post("/login", response_model=TokenOut)
def login(b:Login, db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=b.email).first()
    if not u or not u.password_hash or not verify_pw(b.password,u.password_hash):
        raise HTTPException(401,"Invalid credentials")
    return {"access_token":make_token(u.id,u.role),"user":_user_dict(u)}

@router.post("/forgot-password")
def forgot(payload:dict, db:Session=Depends(get_db)):
    # TODO: send email via SES/SMTP. Here we just acknowledge.
    return {"ok":True}

@router.get("/google")
def google_start():
    if not settings.GOOGLE_CLIENT_ID: raise HTTPException(400,"Google OAuth not configured")
    from urllib.parse import urlencode
    q=urlencode({"client_id":settings.GOOGLE_CLIENT_ID,"redirect_uri":settings.GOOGLE_REDIRECT_URI,
                 "response_type":"code","scope":"openid email profile"})
    return {"url":f"https://accounts.google.com/o/oauth2/v2/auth?{q}"}

@router.get("/google/callback")
async def google_cb(code:str, db:Session=Depends(get_db)):
    async with httpx.AsyncClient() as c:
        tok=await c.post("https://oauth2.googleapis.com/token", data={
            "code":code,"client_id":settings.GOOGLE_CLIENT_ID,"client_secret":settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri":settings.GOOGLE_REDIRECT_URI,"grant_type":"authorization_code"})
        tok.raise_for_status(); at=tok.json()["access_token"]
        prof=(await c.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization":"Bearer "+at})).json()
    u=db.query(User).filter_by(email=prof["email"]).first()
    if not u:
        u=User(name=prof.get("name") or prof["email"], email=prof["email"], google_sub=prof["sub"], role="user")
        db.add(u); db.commit(); db.refresh(u)
    return {"access_token":make_token(u.id,u.role),"user":_user_dict(u)}
