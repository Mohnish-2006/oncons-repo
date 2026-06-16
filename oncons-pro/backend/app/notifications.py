from email.message import EmailMessage
from pathlib import Path
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


def send_email(to_email: str, subject: str, body: str):
    sent = _send_email(to_email, subject, body)
    if sent:
        return True
    outbox = Path("email_outbox")
    outbox.mkdir(exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in to_email)
    (outbox / f"{safe_name}.txt").write_text(
        f"To: {to_email}\nSubject: {subject}\n\n{body}\n",
        encoding="utf-8",
    )
    return False


def send_email_with_attachment(to_email: str, subject: str, body: str, filename: str, data: bytes, mime_type: str = "application/pdf"):
    if mime_type == "application/pdf" and not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    sent = _send_email(to_email, subject, body, [(filename, data, mime_type)])
    outbox = Path("email_outbox")
    outbox.mkdir(exist_ok=True)
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in to_email)
    (outbox / f"{safe_name}_{filename}").write_bytes(data)
    if sent:
        return True
    (outbox / f"{safe_name}_{filename}.txt").write_text(
        f"To: {to_email}\nSubject: {subject}\n\n{body}\n\nAttachment saved: {filename}.pdf\n",
        encoding="utf-8",
    )
    return False


def _send_email(to_email: str, subject: str, body: str, attachments=None):
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD and settings.FROM_EMAIL):
        return False
    msg = EmailMessage()
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, data, mime_type in attachments or []:
        maintype, subtype = mime_type.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
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
