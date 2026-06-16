from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime

class Register(BaseModel):
    name:str; email:EmailStr; password:str; role:str="user"; otp:str
class Login(BaseModel):
    email:EmailStr; password:str
class TokenOut(BaseModel):
    access_token:str; user:dict

class ExpertOut(BaseModel):
    id:int; name:str; category:str; bio:Optional[str]=None
    years_experience:int=0; fee:float=0; rating:float=0; verified:bool=False
    class Config: from_attributes=True

class BookingIn(BaseModel):
    expert_id:int; scheduled_at:datetime; mode:str="video"
class ConsultantRegister(BaseModel):
    name:str
    email:EmailStr
    phone:str
    password:str
    category:str
    bio:str
    years_experience:int=0
    fee:float=0
    city:Optional[str]=None
    languages:Optional[str]=None
    otp:str
    profile_photo_url:Optional[str]=None
    aadhaar_url:Optional[str]=None
    certificate_url:Optional[str]=None
    portfolio_url:Optional[str]=None
class OTPSendIn(BaseModel):
    email:EmailStr
    phone:Optional[str]=None
    purpose:str="consultant_registration"
class SocialLoginIn(BaseModel):
    email:EmailStr
    name:Optional[str]=None
    provider:str="google"
class ReviewIn(BaseModel):
    expert_id:int; rating:int; comment:str
class AIChatIn(BaseModel):
    messages: List[dict]
class CheckoutIn(BaseModel):
    plan:str; provider:str="razorpay"
    booking_id:Optional[int]=None
    purpose:Optional[str]=None
    expert_id:Optional[int]=None
    call_minutes:Optional[int]=None
class ContactIn(BaseModel):
    name:str; email:EmailStr; message:str
class ProfilePatch(BaseModel):
    name:Optional[str]=None; email:Optional[EmailStr]=None; phone:Optional[str]=None; avatar_url:Optional[str]=None
