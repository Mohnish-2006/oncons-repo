from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Expert, UserSession, PasswordResetToken
from ..models import OTPVerification
from ..schemas import Register, Login, TokenOut, ConsultantRegister, OTPSendIn, SocialLoginIn, RefreshIn, ForgotPasswordIn, ResetPasswordIn
from ..auth import hash_pw, verify_pw, make_token, create_session, hash_refresh_token, new_refresh_token, validate_password_strength, current_user, bearer, decode_access_token, utcnow
import httpx
from ..config import settings
from ..notifications import send_email
from datetime import datetime, timedelta
import random
import json
import secrets
from urllib.parse import quote

router = APIRouter()

def _user_dict(u:User): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"plan":u.plan}

def _client_ip(request:Request)->str:
    forwarded=(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")

def _issue_tokens(db:Session, u:User, request:Request, device_id:str=None):
    session, refresh_token=create_session(
        db, u,
        device_id=device_id,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    return {
        "access_token":make_token(u.id,u.role,session.id),
        "refresh_token":refresh_token,
        "token_type":"bearer",
        "expires_in":settings.JWT_EXP_MIN*60,
        "user":_user_dict(u),
    }

CERTIFICATE_REQUIRED_CATEGORIES = {
    "doctor", "psychiatrist", "therapist", "lawyer", "financial advisor",
    "nutritionist", "architect", "interior designer",
}

def _needs_certificate(category: str) -> bool:
    return (category or "").strip().lower() in CERTIFICATE_REQUIRED_CATEGORIES

@router.post("/register", response_model=TokenOut)
def register(b:Register, request:Request, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=b.email).first(): raise HTTPException(400,"Email already registered")
    validate_password_strength(b.password)
    otp=db.query(OTPVerification).filter_by(email=b.email, purpose="user_registration", code=b.otp).order_by(OTPVerification.id.desc()).first()
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400,"Invalid or expired OTP")
    otp.verified=True
    u=User(name=b.name,email=b.email,password_hash=hash_pw(b.password),role=b.role if b.role in("user","expert") else "user")
    db.add(u); db.flush()
    if u.role=="expert":
        db.add(Expert(user_id=u.id, name=u.name, category="General"))
    db.commit(); db.refresh(u)
    return _issue_tokens(db,u,request)

@router.post("/otp/send")
def send_otp(b:OTPSendIn, db:Session=Depends(get_db)):
    code=f"{random.randint(100000,999999)}"
    otp=OTPVerification(email=b.email, phone=b.phone, purpose=b.purpose, code=code,
                        expires_at=utcnow()+timedelta(minutes=10))
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
def consultant_register(b:ConsultantRegister, request:Request, db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=b.email).first():
        raise HTTPException(400,"Email already registered")
    validate_password_strength(b.password)
    otp=db.query(OTPVerification).filter_by(email=b.email, purpose="consultant_registration", code=b.otp).order_by(OTPVerification.id.desc()).first()
    if not otp or otp.expires_at < datetime.utcnow():
        raise HTTPException(400,"Invalid or expired OTP")
    certificate_required=_needs_certificate(b.category)
    if certificate_required and not b.certificate_url:
        raise HTTPException(400, f"{b.category} requires certificate proof before registration.")
    otp.verified=True
    u=User(name=b.name,email=b.email,phone=b.phone,password_hash=hash_pw(b.password),role="expert")
    db.add(u); db.flush()
    application_status="pending" if certificate_required else "approved"
    e=Expert(user_id=u.id, name=b.name, category=b.category, bio=b.bio,
             years_experience=b.years_experience, fee=b.fee, city=b.city,
             languages=b.languages, profile_photo_url=b.profile_photo_url,
             aadhaar_url=b.aadhaar_url, certificate_url=b.certificate_url,
             portfolio_url=b.portfolio_url,
             certificate_required=certificate_required,
             certificate_verified=False,
             verified=not certificate_required, available=True,
             application_status=application_status, aadhaar_verified=False)
    db.add(e); db.commit(); db.refresh(u)
    return _issue_tokens(db,u,request)

@router.post("/login", response_model=TokenOut)
def login(b:Login, request:Request, db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=b.email).first()
    if not u or not u.password_hash or not verify_pw(b.password,u.password_hash):
        raise HTTPException(401,"Invalid credentials")
    return _issue_tokens(db,u,request)

@router.post("/social-login", response_model=TokenOut)
def social_login(b:SocialLoginIn, request:Request, db:Session=Depends(get_db)):
    provider=(b.provider or "google").lower()
    if provider not in ("google", "apple"):
        raise HTTPException(400, "Unsupported sign-in provider")
    u=db.query(User).filter_by(email=b.email).first()
    if not u:
        u=User(name=b.name or b.email.split("@")[0], email=b.email, role="user")
        if provider=="google":
            u.google_sub=b.email
        db.add(u); db.commit(); db.refresh(u)
    return _issue_tokens(db,u,request)

@router.post("/refresh", response_model=TokenOut)
def refresh(b:RefreshIn, request:Request, db:Session=Depends(get_db)):
    session=db.query(UserSession).filter_by(refresh_token_hash=hash_refresh_token(b.refresh_token), revoked=False).first()
    if not session or session.expires_at < utcnow():
        raise HTTPException(401, "Refresh token expired")
    u=db.get(User, session.user_id)
    if not u:
        raise HTTPException(401, "User not found")
    refresh_token=new_refresh_token()
    session.refresh_token_hash=hash_refresh_token(refresh_token)
    session.last_seen_at=utcnow()
    session.user_agent=(request.headers.get("user-agent") or "")[:255]
    session.ip_address=_client_ip(request)[:64]
    db.commit()
    return {
        "access_token":make_token(u.id,u.role,session.id),
        "refresh_token":refresh_token,
        "token_type":"bearer",
        "expires_in":settings.JWT_EXP_MIN*60,
        "user":_user_dict(u),
    }

@router.post("/logout")
def logout(request:Request, u:User=Depends(current_user), db:Session=Depends(get_db)):
    auth=request.headers.get("authorization") or ""
    token=auth.removeprefix("Bearer ").removeprefix("bearer ").strip()
    if token:
        data=decode_access_token(token)
        sid=data.get("sid")
        if sid:
            session=db.query(UserSession).filter_by(id=int(sid), user_id=u.id).first()
            if session:
                session.revoked=True
                db.commit()
    return {"ok":True}

@router.post("/logout-all")
def logout_all(u:User=Depends(current_user), db:Session=Depends(get_db)):
    db.query(UserSession).filter_by(user_id=u.id, revoked=False).update({"revoked":True})
    db.commit()
    return {"ok":True}

@router.post("/forgot-password")
def forgot(payload:ForgotPasswordIn, db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=payload.email).first()
    if u:
        raw_token=secrets.token_urlsafe(40)
        reset=PasswordResetToken(
            user_id=u.id,
            token_hash=hash_refresh_token(raw_token),
            expires_at=utcnow()+timedelta(hours=1),
        )
        db.add(reset); db.commit()
        link=f"{settings.FRONTEND_URL}/forgot-password.html?token={quote(raw_token)}"
        body=(
            f"Hi {u.name},\n\n"
            "Use this secure link to reset your OnCons password. It expires in 1 hour.\n\n"
            f"{link}\n\n"
            "If you did not request this, ignore this email."
        )
        send_email(u.email, "Reset your OnCons password", body)
    return {"ok":True}

@router.post("/reset-password")
def reset_password(payload:ResetPasswordIn, db:Session=Depends(get_db)):
    validate_password_strength(payload.password)
    token_hash=hash_refresh_token(payload.token)
    reset=db.query(PasswordResetToken).filter_by(token_hash=token_hash, used=False).first()
    if not reset or reset.expires_at < utcnow():
        raise HTTPException(400,"Invalid or expired reset token")
    u=db.get(User, reset.user_id)
    if not u:
        raise HTTPException(404,"User not found")
    u.password_hash=hash_pw(payload.password)
    reset.used=True
    db.query(UserSession).filter_by(user_id=u.id, revoked=False).update({"revoked":True})
    db.commit()
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
    session, refresh_token=create_session(db,u,user_agent="google-oauth")
    token=make_token(u.id,u.role,session.id)
    user=quote(json.dumps(_user_dict(u)))
    return RedirectResponse(f"{settings.FRONTEND_URL}/oauth-callback.html?token={token}&refresh_token={refresh_token}&user={user}")
