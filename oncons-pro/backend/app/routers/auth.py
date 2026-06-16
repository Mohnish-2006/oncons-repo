from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Expert
from ..models import OTPVerification
from ..schemas import Register, Login, TokenOut, ConsultantRegister, OTPSendIn, SocialLoginIn
from ..auth import hash_pw, verify_pw, make_token
import httpx
from ..config import settings
from ..notifications import send_email
from datetime import datetime, timedelta
import random
import json
from urllib.parse import quote

router = APIRouter()

def _user_dict(u:User): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"plan":u.plan}

CERTIFICATE_REQUIRED_CATEGORIES = {
    "doctor", "psychiatrist", "therapist", "lawyer", "financial advisor",
    "nutritionist", "architect", "interior designer",
}

def _needs_certificate(category: str) -> bool:
    return (category or "").strip().lower() in CERTIFICATE_REQUIRED_CATEGORIES

@router.post("/register", response_model=TokenOut)
def register(b:Register, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=b.email).first(): raise HTTPException(400,"Email already registered")
    otp=db.query(OTPVerification).filter_by(email=b.email, purpose="user_registration", code=b.otp).order_by(OTPVerification.id.desc()).first()
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400,"Invalid or expired OTP")
    otp.verified=True
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
    body=(
        f"Your OnCons registration OTP is {code}.\n\n"
        "This code is valid for 10 minutes. Do not share it with anyone."
    )
    delivered=send_email(b.email, "Your OnCons registration OTP", body)
    if settings.OTP_REQUIRE_EMAIL_DELIVERY and not delivered:
        raise HTTPException(503, "Email is not configured. Add SMTP settings in backend/.env to send OTP mail.")
    response={"ok":True, "email_sent":delivered, "message":"OTP sent to the email address entered."}
    if not delivered:
        response["dev_otp"]=code
        response["message"]="SMTP is not configured, so the OTP was saved in backend/email_outbox for demo testing."
    return response

@router.post("/consultant/register", response_model=TokenOut)
def consultant_register(b:ConsultantRegister, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=b.email).first():
        raise HTTPException(400,"Email already registered")
    otp=db.query(OTPVerification).filter_by(email=b.email, purpose="consultant_registration", code=b.otp).order_by(OTPVerification.id.desc()).first()
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400,"Invalid or expired OTP")
    certificate_required=_needs_certificate(b.category)
    if certificate_required and not b.certificate_url:
        raise HTTPException(400, f"{b.category} requires certificate proof before registration.")
    otp.verified=True
    u=User(name=b.name,email=b.email,phone=b.phone,password_hash=hash_pw(b.password),role="expert")
    db.add(u); db.flush()
    e=Expert(user_id=u.id, name=b.name, category=b.category, bio=b.bio,
             years_experience=b.years_experience, fee=b.fee, city=b.city,
             languages=b.languages, profile_photo_url=b.profile_photo_url,
             aadhaar_url=b.aadhaar_url, certificate_url=b.certificate_url,
             portfolio_url=b.portfolio_url,
             certificate_required=certificate_required,
             certificate_verified=certificate_required,
             verified=True, available=True,
             application_status="approved", aadhaar_verified=False)
    db.add(e); db.commit(); db.refresh(u)
    return {"access_token":make_token(u.id,u.role),"user":_user_dict(u)}

@router.post("/login", response_model=TokenOut)
def login(b:Login, db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=b.email).first()
    if not u or not u.password_hash or not verify_pw(b.password,u.password_hash):
        raise HTTPException(401,"Invalid credentials")
    return {"access_token":make_token(u.id,u.role),"user":_user_dict(u)}

@router.post("/social-login", response_model=TokenOut)
def social_login(b:SocialLoginIn, db:Session=Depends(get_db)):
    provider=(b.provider or "google").lower()
    if provider not in ("google", "apple"):
        raise HTTPException(400, "Unsupported sign-in provider")
    u=db.query(User).filter_by(email=b.email).first()
    if not u:
        u=User(name=b.name or b.email.split("@")[0], email=b.email, role="user")
        if provider=="google":
            u.google_sub=b.email
        db.add(u); db.commit(); db.refresh(u)
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
    token=make_token(u.id,u.role)
    user=quote(json.dumps(_user_dict(u)))
    return RedirectResponse(f"{settings.FRONTEND_URL}/oauth-callback.html?token={token}&user={user}")
