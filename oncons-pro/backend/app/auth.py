from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import hashlib
import secrets
import re
from .db import get_db
from .config import settings
from .models import User, UserSession

pwd = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

def hash_pw(p): return pwd.hash(p)
def verify_pw(p, h): return pwd.verify(p, h)

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def hash_refresh_token(token:str)->str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def new_refresh_token()->str:
    return secrets.token_urlsafe(48)

def validate_password_strength(password:str):
    if len(password or "") < 10:
        raise HTTPException(400, "Password must be at least 10 characters")
    checks=[
        (r"[A-Z]", "one uppercase letter"),
        (r"[a-z]", "one lowercase letter"),
        (r"\d", "one number"),
        (r"[^A-Za-z0-9]", "one symbol"),
    ]
    missing=[label for pattern,label in checks if not re.search(pattern, password)]
    if missing:
        raise HTTPException(400, "Password must include " + ", ".join(missing))
    if password.lower() in {"password123!", "admin12345!", "oncons123!"}:
        raise HTTPException(400, "Choose a less common password")

def create_session(db:Session, user:User, device_id:str=None, user_agent:str=None, ip_address:str=None):
    refresh_token=new_refresh_token()
    session=UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        device_id=device_id,
        user_agent=(user_agent or "")[:255],
        ip_address=(ip_address or "")[:64],
        expires_at=utcnow()+timedelta(days=settings.REFRESH_TOKEN_DAYS),
    )
    db.add(session); db.commit(); db.refresh(session)
    return session, refresh_token

def make_token(uid:int, role:str, session_id:int=None):
    payload={"sub":str(uid),"role":role,"exp":utcnow()+timedelta(minutes=settings.JWT_EXP_MIN)}
    if session_id:
        payload["sid"]=str(session_id)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)

def decode_access_token(token:str)->dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO])
    except JWTError:
        raise HTTPException(401,"Invalid token")

def current_user(cred:HTTPAuthorizationCredentials=Depends(bearer), db:Session=Depends(get_db))->User:
    if not cred: raise HTTPException(401,"Missing token")
    try:
        data=decode_access_token(cred.credentials)
        uid=int(data["sub"])
    except (JWTError, ValueError):
        raise HTTPException(401,"Invalid token")
    sid=data.get("sid")
    if sid:
        try:
            sid_int=int(sid)
        except ValueError:
            raise HTTPException(401,"Invalid session")
        session=db.query(UserSession).filter_by(id=sid_int, user_id=uid).first()
        if not session or session.revoked or session.expires_at < utcnow():
            raise HTTPException(401,"Session expired")
        session.last_seen_at=utcnow()
        db.commit()
    u=db.get(User, uid)
    if not u: raise HTTPException(401,"User not found")
    return u

def require_role(*roles):
    def dep(u:User=Depends(current_user)):
        if u.role not in roles and u.role!="admin":
            raise HTTPException(403,"Forbidden")
        return u
    return dep
