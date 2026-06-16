from sqlalchemy import (Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, Enum, JSON)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .db import Base

class Role(str, enum.Enum):
    user="user"; expert="expert"; admin="admin"

class User(Base):
    __tablename__="users"
    id=Column(Integer, primary_key=True)
    name=Column(String, nullable=False)
    email=Column(String, unique=True, index=True, nullable=False)
    phone=Column(String)
    password_hash=Column(String)
    role=Column(String, default="user")
    avatar_url=Column(String)
    google_sub=Column(String, index=True)
    plan=Column(String, default="free")  # free|pro|premium
    created_at=Column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__="categories"
    id=Column(Integer, primary_key=True)
    name=Column(String, unique=True)
    icon=Column(String)

class Expert(Base):
    __tablename__="experts"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"), unique=True)
    name=Column(String)
    category=Column(String, index=True)
    bio=Column(Text)
    years_experience=Column(Integer, default=0)
    fee=Column(Float, default=0)
    rating=Column(Float, default=0)
    verified=Column(Boolean, default=False)
    available=Column(Boolean, default=True)
    city=Column(String)
    languages=Column(String)
    profile_photo_url=Column(String)
    aadhaar_url=Column(String)
    application_status=Column(String, default="approved")  # draft|pending|approved|rejected
    aadhaar_verified=Column(Boolean, default=False)

class Availability(Base):
    __tablename__="availability"
    id=Column(Integer, primary_key=True)
    expert_id=Column(Integer, ForeignKey("experts.id"), unique=True)
    days=Column(String, default="Mon,Tue,Wed,Thu,Fri")
    from_time=Column(String, default="09:00")
    to_time=Column(String, default="18:00")

class Booking(Base):
    __tablename__="bookings"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    expert_id=Column(Integer, ForeignKey("experts.id"))
    scheduled_at=Column(DateTime)
    status=Column(String, default="pending")  # pending|confirmed|completed|cancelled
    fee=Column(Float, default=0)
    meeting_token=Column(String, index=True)
    free_minutes=Column(Integer, default=2)
    rate_per_minute=Column(Float, default=25)
    call_started_at=Column(DateTime)
    call_ended_at=Column(DateTime)
    billable_minutes=Column(Integer, default=0)
    call_charge_status=Column(String, default="not_started")  # not_started|free|payment_due|paid
    details_unlocked=Column(Boolean, default=False)
    created_at=Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__="payments"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    booking_id=Column(Integer, ForeignKey("bookings.id"), nullable=True)
    amount=Column(Float)
    currency=Column(String, default="INR")
    provider=Column(String)  # razorpay|stripe
    provider_ref=Column(String)
    status=Column(String, default="initiated")
    description=Column(String)
    created_at=Column(DateTime, default=datetime.utcnow)

class OTPVerification(Base):
    __tablename__="otp_verifications"
    id=Column(Integer, primary_key=True)
    email=Column(String, index=True)
    phone=Column(String, index=True)
    purpose=Column(String, default="consultant_registration")
    code=Column(String)
    verified=Column(Boolean, default=False)
    expires_at=Column(DateTime)
    created_at=Column(DateTime, default=datetime.utcnow)

class Subscription(Base):
    __tablename__="subscriptions"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    plan=Column(String)  # free|pro|premium
    status=Column(String, default="active")
    renews_at=Column(DateTime)
    provider=Column(String)
    provider_ref=Column(String)
    created_at=Column(DateTime, default=datetime.utcnow)

class Review(Base):
    __tablename__="reviews"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    expert_id=Column(Integer, ForeignKey("experts.id"))
    rating=Column(Integer)
    comment=Column(Text)
    ai_summary=Column(Text)
    helpful=Column(Integer, default=0)
    created_at=Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__="messages"
    id=Column(Integer, primary_key=True)
    booking_id=Column(Integer, ForeignKey("bookings.id"))
    sender_id=Column(Integer, ForeignKey("users.id"))
    content=Column(Text)
    created_at=Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__="notifications"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    title=Column(String)
    body=Column(Text)
    read=Column(Boolean, default=False)
    created_at=Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__="transactions"
    id=Column(Integer, primary_key=True)
    payment_id=Column(Integer, ForeignKey("payments.id"))
    type=Column(String)  # credit|debit|refund|payout
    amount=Column(Float)
    meta=Column(JSON)
    created_at=Column(DateTime, default=datetime.utcnow)

class AIChat(Base):
    __tablename__="ai_chats"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"))
    messages=Column(JSON)  # [{role,content}]
    created_at=Column(DateTime, default=datetime.utcnow)

class SupportTicket(Base):
    __tablename__="support_tickets"
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey("users.id"), nullable=True)
    email=Column(String)
    subject=Column(String)
    body=Column(Text)
    status=Column(String, default="open")
    created_at=Column(DateTime, default=datetime.utcnow)

class AdminLog(Base):
    __tablename__="admin_logs"
    id=Column(Integer, primary_key=True)
    admin_id=Column(Integer, ForeignKey("users.id"))
    action=Column(String)
    meta=Column(JSON)
    created_at=Column(DateTime, default=datetime.utcnow)
