from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .db import get_db
from .config import settings
from .models import User

pwd = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

def hash_pw(p): return pwd.hash(p)
def verify_pw(p, h): return pwd.verify(p, h)

def make_token(uid:int, role:str):
    payload={"sub":str(uid),"role":role,"exp":datetime.utcnow()+timedelta(minutes=settings.JWT_EXP_MIN)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)

def current_user(cred:HTTPAuthorizationCredentials=Depends(bearer), db:Session=Depends(get_db))->User:
    if not cred: raise HTTPException(401,"Missing token")
    try:
        data=jwt.decode(cred.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGO])
        uid=int(data["sub"])
    except (JWTError, ValueError):
        raise HTTPException(401,"Invalid token")
    u=db.query(User).get(uid)
    if not u: raise HTTPException(401,"User not found")
    return u

def require_role(*roles):
    def dep(u:User=Depends(current_user)):
        if u.role not in roles and u.role!="admin":
            raise HTTPException(403,"Forbidden")
        return u
    return dep
