import os
import uuid
import hmac
import json
import hashlib
from datetime import datetime, timedelta

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_oncons_security.db")
os.environ.setdefault("JWT_SECRET", "test-secret-change-me")

from fastapi.testclient import TestClient

from app.auth import hash_pw, hash_refresh_token, utcnow
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import PasswordResetToken, Payment, User
from app.config import settings


client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def unique_email(prefix="user"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def create_user(role="user"):
    email = unique_email(role)
    with SessionLocal() as db:
        user = User(
            name=f"{role.title()} Test",
            email=email,
            password_hash=hash_pw("StrongPass1!"),
            role=role,
        )
        db.add(user)
        db.commit()
    return email


def login(email):
    res = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1!"})
    assert res.status_code == 200, res.text
    return res.json()


def test_password_policy_rejects_weak_password_before_otp_check():
    res = client.post(
        "/api/auth/register",
        json={"name": "Weak", "email": unique_email(), "password": "short", "role": "user", "otp": "000000"},
    )
    assert res.status_code == 400
    assert "Password" in res.json()["detail"]


def test_refresh_token_rotates_and_logout_all_revokes_session():
    tokens = login(create_user())
    assert tokens["refresh_token"]

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    rotated = refreshed.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    logout = client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {rotated['access_token']}"})
    assert logout.status_code == 200, logout.text

    denied = client.post("/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert denied.status_code == 401


def test_reset_password_updates_password_and_revokes_sessions():
    email = create_user()
    tokens = login(email)
    raw_token = "reset-" + uuid.uuid4().hex
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).first()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_token),
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        db.commit()

    res = client.post("/api/auth/reset-password", json={"token": raw_token, "password": "BetterPass1!"})
    assert res.status_code == 200, res.text

    old_refresh = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert old_refresh.status_code == 401

    old_login = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1!"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": email, "password": "BetterPass1!"})
    assert new_login.status_code == 200, new_login.text


def test_production_rejects_demo_payments_without_creating_payment(monkeypatch):
    tokens = login(create_user())
    before = None
    with SessionLocal() as db:
        before = db.query(Payment).count()

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    res = client.post(
        "/api/payments/checkout",
        json={"plan": "pro", "provider": "upi"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == 400

    with SessionLocal() as db:
        assert db.query(Payment).count() == before


def test_authenticated_upload_accepts_image():
    tokens = login(create_user())
    res = client.post(
        "/api/uploads",
        files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["url"].endswith(".png")


def test_admin_can_record_demo_refund():
    user_email = create_user()
    admin_email = create_user("admin")
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=user_email).first()
        payment = Payment(user_id=user.id, amount=100, provider="upi", status="paid", description="Pro plan")
        db.add(payment)
        db.commit()
        payment_id = payment.id

    tokens = login(admin_email)
    res = client.post(
        f"/api/payments/{payment_id}/refund",
        json={"amount": 40},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "partially_refunded"


def test_razorpay_verify_marks_payment_paid_and_activates_plan(monkeypatch):
    tokens = login(create_user())
    order_id = "order_" + uuid.uuid4().hex[:10]
    razorpay_payment_id = "pay_" + uuid.uuid4().hex[:10]
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp-test-secret")
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=tokens["user"]["email"]).first()
        payment = Payment(
            user_id=user.id,
            amount=499,
            provider="razorpay",
            provider_ref=order_id,
            status="initiated",
            description="Pro plan",
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

    signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    res = client.post(
        "/api/payments/razorpay/verify",
        json={
            "payment_id": payment_id,
            "razorpay_order_id": order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": signature,
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == 200, res.text
    with SessionLocal() as db:
        payment = db.get(Payment, payment_id)
        user = db.query(User).filter_by(email=tokens["user"]["email"]).first()
        assert payment.status == "paid"
        assert payment.provider_ref == razorpay_payment_id
        assert user.plan == "pro"


def test_razorpay_verify_rejects_bad_signature(monkeypatch):
    tokens = login(create_user())
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "rzp-test-secret")
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=tokens["user"]["email"]).first()
        payment = Payment(
            user_id=user.id,
            amount=499,
            provider="razorpay",
            provider_ref="order_bad_sig",
            status="initiated",
            description="Pro plan",
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

    res = client.post(
        "/api/payments/razorpay/verify",
        json={
            "payment_id": payment_id,
            "razorpay_order_id": "order_bad_sig",
            "razorpay_payment_id": "pay_bad_sig",
            "razorpay_signature": "not-valid",
        },
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert res.status_code == 400
    with SessionLocal() as db:
        assert db.get(Payment, payment_id).status == "initiated"


def test_razorpay_webhook_marks_payment_paid(monkeypatch):
    email = create_user()
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "webhook-secret")
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).first()
        payment = Payment(
            user_id=user.id,
            amount=1499,
            provider="razorpay",
            provider_ref="order_webhook",
            status="initiated",
            description="Premium plan",
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id

    body = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_webhook",
                    "order_id": "order_webhook",
                    "status": "captured",
                    "notes": {"payment_id": str(payment_id)},
                }
            }
        },
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    res = client.post(
        "/api/payments/razorpay/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
    )
    assert res.status_code == 200, res.text
    with SessionLocal() as db:
        payment = db.get(Payment, payment_id)
        user = db.query(User).filter_by(email=email).first()
        assert payment.status == "paid"
        assert payment.provider_ref == "pay_webhook"
        assert user.plan == "premium"
