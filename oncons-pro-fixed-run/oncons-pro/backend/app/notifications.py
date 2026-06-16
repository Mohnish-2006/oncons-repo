from email.message import EmailMessage
import smtplib
import urllib.parse

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .models import Notification, User


def notify_user(db: Session, user_id: int, title: str, body: str):
    db.add(Notification(user_id=user_id, title=title, body=body))


def notify_expert_booking(db: Session, expert_user: User, customer: User, when, join_path: str):
    body = (
        f"{customer.name} needs your help on OnCons.\n"
        f"Scheduled time: {when}\n"
        f"Customer phone: {customer.phone or 'Not provided'}\n"
        f"Join room: {settings.FRONTEND_URL}{join_path}"
    )
    notify_user(db, expert_user.id, "New student/customer request", body)
    try:
        _send_email(expert_user.email, "New OnCons request", body)
    except Exception:
        pass
    if expert_user.phone:
        try:
            _send_sms(expert_user.phone, body)
        except Exception:
            pass


def _send_email(to_email: str, subject: str, body: str):
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD and settings.FROM_EMAIL):
        return False
    msg = EmailMessage()
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    return True


def _send_sms(phone: str, body: str):
    if not settings.SMS_WEBHOOK_URL:
        return False
    url = settings.SMS_WEBHOOK_URL
    url = url.replace("{phone}", urllib.parse.quote(phone))
    url = url.replace("{message}", urllib.parse.quote(body[:300]))
    try:
        httpx.get(url, timeout=8)
        return True
    except Exception:
        return False
