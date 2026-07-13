from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Payment, Subscription, User, Booking, Expert, Notification, Invoice, Transaction
from ..auth import current_user, require_role
from ..schemas import CheckoutIn
from ..config import settings
from ..notifications import notify_expert_booking, send_email_with_attachment
from ..billing import booking_bill_pdf
from datetime import datetime, timedelta
from ..auth import utcnow
import re
import hmac
import hashlib
import json

router=APIRouter()
PLAN_AMOUNTS={"free":0,"pro":499,"premium":1499}
CALL_PACKAGES={10:49,15:69,30:129}

def _is_production() -> bool:
    return settings.ENVIRONMENT.strip().lower() in {"prod", "production"}

def _demo_payments_enabled() -> bool:
    return not _is_production() and settings.PAYMENT_AUTO_VERIFY_SECONDS > 0

@router.post("/checkout")
def checkout(b:CheckoutIn, u:User=Depends(current_user), db:Session=Depends(get_db)):
    if b.purpose=="call_charge":
        booking=db.query(Booking).filter_by(id=b.booking_id,user_id=u.id).first()
        if not booking: raise HTTPException(404,"Booking not found")
        if u.plan=="premium":
            booking.call_charge_status="paid"
            db.commit()
            raise HTTPException(400,"Premium+ includes free video calls")
        minutes=b.call_minutes or (booking.billable_minutes if booking.billable_minutes in CALL_PACKAGES else 10)
        if minutes not in CALL_PACKAGES:
            raise HTTPException(400,"Choose a valid call package")
        booking.billable_minutes=minutes
        db.commit()
        amt=CALL_PACKAGES[minutes]
        if amt <= 0: raise HTTPException(400,"No call charge due")
        desc=f"Call charge for booking #{booking.id} - {minutes} minutes"
    elif b.purpose=="details":
        expert=db.get(Expert, b.expert_id)
        if not expert or expert.application_status!="approved": raise HTTPException(404,"Consultant not found")
        amt=settings.DETAILS_UNLOCK_AMOUNT
        desc=f"Expert details #{expert.id}"
    elif b.booking_id:
        booking=db.query(Booking).filter_by(id=b.booking_id,user_id=u.id).first()
        if not booking: raise HTTPException(404,"Booking not found")
        amt=booking.fee
        desc=f"Consultation booking #{booking.id}"
    else:
        amt=PLAN_AMOUNTS.get(b.plan)
        if amt is None: raise HTTPException(400,"Bad plan")
        desc=f"{b.plan.title()} plan"
    if _is_production() and b.provider in ("upi", "debit_card", "credit_card"):
        raise HTTPException(400, "Demo payment methods are disabled in production. Use Razorpay or Stripe.")
    p=Payment(user_id=u.id, booking_id=b.booking_id, amount=amt, provider=b.provider, status="initiated", description=desc)
    db.add(p); db.commit(); db.refresh(p)
    if b.provider=="upi":
        upi_url=""
        if settings.UPI_ID:
            from urllib.parse import quote
            upi_url=f"upi://pay?pa={quote(settings.UPI_ID)}&pn={quote(settings.UPI_PAYEE_NAME)}&am={amt}&cu=INR&tn={quote(desc)}"
        return {"payment_id":p.id,"amount":amt,"currency":"INR","provider":"upi",
                "upi_id":settings.UPI_ID,"upi_url":upi_url,"qr_url":settings.PAYMENT_QR_URL,
                "note":"Set UPI_ID and PAYMENT_QR_URL in backend/.env to receive money in your bank account."}
    if b.provider in ("debit_card", "credit_card"):
        return {"payment_id":p.id,"amount":amt,"currency":"INR","provider":b.provider,
                "note":"Demo card payment created. The backend verifies it automatically for the classroom demo."}
    # Razorpay/Stripe order creation goes here. Return stub URL for now.
    if b.provider=="razorpay":
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(503, "Razorpay is not configured")
        try:
            import razorpay
            client=razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order=client.order.create({"amount":int(amt*100),"currency":"INR","receipt":f"pmt_{p.id}","notes":{"payment_id":str(p.id)}})
            p.provider_ref=order["id"]; db.commit()
            return {
                "payment_id":p.id,
                "amount":amt,
                "currency":"INR",
                "provider":"razorpay",
                "order_id":order["id"],
                "key":settings.RAZORPAY_KEY_ID,
                "name":"OnCons",
                "description":desc,
                "user":{"name":u.name,"email":u.email,"phone":u.phone or ""},
            }
        except Exception as e:
            if _is_production():
                raise HTTPException(502, "Razorpay order creation failed")
            return {"checkout_url":f"https://stub.local/razorpay/{p.id}","note":str(e)}
    if b.provider=="stripe":
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(503, "Stripe is not configured")
        try:
            import stripe
            stripe.api_key=settings.STRIPE_SECRET_KEY
            sess=stripe.checkout.Session.create(mode="payment",
                line_items=[{"price_data":{"currency":"inr","product_data":{"name":f"{b.plan.title()} plan"},"unit_amount":int(amt*100)},"quantity":1}],
                success_url=settings.FRONTEND_URL+"/dashboard/subscription.html",
                cancel_url=settings.FRONTEND_URL+"/pricing.html")
            p.provider_ref=sess.id; db.commit()
            return {"checkout_url":sess.url}
        except Exception as e:
            if _is_production():
                raise HTTPException(502, "Stripe checkout creation failed")
            return {"checkout_url":f"https://stub.local/stripe/{p.id}","note":str(e)}
    raise HTTPException(400,"Unknown provider")

@router.post("/{pid}/mark-paid")
def mark_paid(pid:int, payload:dict, u:User=Depends(current_user), db:Session=Depends(get_db)):
    if _is_production():
        raise HTTPException(403, "Payments can only be confirmed by verified provider webhooks in production")
    p=db.query(Payment).filter_by(id=pid,user_id=u.id).first()
    if not p: raise HTTPException(404,"Payment not found")
    reference=(payload.get("reference") or "").strip()
    if p.provider=="upi":
        if not re.match(settings.UPI_UTR_REGEX, reference):
            raise HTTPException(400,"Enter the real 12-digit UPI UTR/reference number from your bank app.")
        existing=db.query(Payment).filter(Payment.provider=="upi", Payment.provider_ref==reference, Payment.id!=p.id).first()
        if existing:
            raise HTTPException(400,"This UPI reference number was already used.")
    p.status="paid"
    p.provider_ref=reference or p.provider_ref
    db.commit()
    _activate_plan(db,p)
    return {"ok":True}

@router.get("/{pid}/status")
def payment_status(pid:int, u:User=Depends(current_user), db:Session=Depends(get_db)):
    p=db.query(Payment).filter_by(id=pid,user_id=u.id).first()
    if not p: raise HTTPException(404,"Payment not found")
    # Demo auto-verification for static UPI QR. Real bank verification needs Razorpay/PhonePe/Cashfree/bank webhooks.
    age=(utcnow()-p.created_at).total_seconds()
    if _demo_payments_enabled() and p.provider in ("upi", "debit_card", "credit_card") and p.status=="initiated" and age>=settings.PAYMENT_AUTO_VERIFY_SECONDS:
        p.status="paid"
        p.provider_ref=p.provider_ref or f"AUTO-{p.id}"
        db.commit()
        _activate_plan(db,p)
    return {"id":p.id,"status":p.status,"amount":p.amount,"description":p.description}

@router.post("/razorpay/webhook")
async def rzp_webhook(req:Request, db:Session=Depends(get_db)):
    raw_body=await req.body()
    signature=req.headers.get("X-Razorpay-Signature")
    secret=settings.RAZORPAY_WEBHOOK_SECRET or settings.RAZORPAY_KEY_SECRET
    if not secret:
        raise HTTPException(503, "Razorpay webhook secret is not configured")
    if not signature:
        raise HTTPException(400, "Missing Razorpay signature")
    expected=hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(400, "Invalid Razorpay signature")
    body=json.loads(raw_body.decode("utf-8"))
    entity=body.get("payload",{}).get("payment",{}).get("entity",{})
    notes=entity.get("notes") or {}
    pid=notes.get("payment_id")
    if not pid and entity.get("order_id"):
        payment=db.query(Payment).filter_by(provider="razorpay", provider_ref=entity.get("order_id")).first()
    elif pid:
        payment=db.get(Payment, int(pid))
    else:
        payment=None
    if payment and entity.get("status") in {"captured", "authorized"}:
        payment.status="paid"
        payment.provider_ref=entity.get("id") or payment.provider_ref
        db.commit()
        _activate_plan(db,payment)
    return {"ok":True}

@router.post("/razorpay/verify")
def rzp_verify(payload:dict, u:User=Depends(current_user), db:Session=Depends(get_db)):
    order_id=(payload.get("razorpay_order_id") or "").strip()
    payment_id=(payload.get("razorpay_payment_id") or "").strip()
    signature=(payload.get("razorpay_signature") or "").strip()
    local_payment_id=payload.get("payment_id")
    if not order_id or not payment_id or not signature:
        raise HTTPException(400, "Missing Razorpay verification fields")
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, "Razorpay is not configured")
    expected=hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(400, "Invalid Razorpay payment signature")
    q=db.query(Payment).filter_by(provider="razorpay", provider_ref=order_id, user_id=u.id)
    payment=q.first()
    if not payment and local_payment_id:
        payment=db.query(Payment).filter_by(id=int(local_payment_id), user_id=u.id).first()
        if payment and payment.provider_ref and payment.provider_ref != order_id:
            raise HTTPException(400, "Razorpay order does not match this payment")
    if not payment:
        raise HTTPException(404, "Payment not found")
    payment.status="paid"
    payment.provider_ref=payment_id
    db.commit()
    _activate_plan(db,payment)
    return {"ok":True,"payment_id":payment.id,"status":payment.status}

@router.post("/stripe/webhook")
async def stripe_webhook(req:Request, db:Session=Depends(get_db)):
    raw_body=await req.body()
    sig=req.headers.get("stripe-signature")
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe webhook secret is not configured")
    try:
        import stripe
        event=stripe.Webhook.construct_event(raw_body, sig, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(400, "Invalid Stripe webhook signature") from exc
    if event.get("type")=="checkout.session.completed":
        session=event["data"]["object"]
        payment=db.query(Payment).filter_by(provider="stripe", provider_ref=session.get("id")).first()
        if payment:
            payment.status="paid"
            db.commit()
            _activate_plan(db,payment)
    return {"ok":True}

@router.post("/{pid}/refund")
def refund_payment(pid:int, payload:dict, admin:User=Depends(require_role("admin")), db:Session=Depends(get_db)):
    payment=db.get(Payment, pid)
    if not payment:
        raise HTTPException(404,"Payment not found")
    if payment.status not in ("paid","refunded","partially_refunded"):
        raise HTTPException(400,"Only paid payments can be refunded")
    amount=float(payload.get("amount") or payment.amount or 0)
    if amount <= 0 or amount > (payment.amount or 0) - (payment.refunded_amount or 0):
        raise HTTPException(400,"Invalid refund amount")
    refund_ref=""
    if payment.provider=="razorpay" and _is_production():
        import razorpay
        client=razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        refund=client.payment.refund(payment.provider_ref, {"amount":int(amount*100)})
        refund_ref=refund.get("id","")
    elif payment.provider=="stripe" and _is_production():
        import stripe
        stripe.api_key=settings.STRIPE_SECRET_KEY
        refund=stripe.Refund.create(payment_intent=payment.provider_ref, amount=int(amount*100))
        refund_ref=refund.get("id","")
    else:
        refund_ref=f"DEMO-REFUND-{payment.id}-{int(utcnow().timestamp())}"
    payment.refunded_amount=(payment.refunded_amount or 0)+amount
    payment.refund_ref=refund_ref
    payment.status="refunded" if payment.refunded_amount >= (payment.amount or 0) else "partially_refunded"
    db.add(Transaction(payment_id=payment.id, type="refund", amount=amount, meta={"refund_ref":refund_ref,"admin_id":admin.id}))
    db.commit()
    return {"ok":True,"status":payment.status,"refund_ref":refund_ref,"refunded_amount":payment.refunded_amount}

def _activate_plan(db, payment:Payment):
    _issue_invoice(db, payment)
    desc=payment.description or ""
    if desc.startswith("Consultation booking #") and payment.booking_id:
        booking=db.get(Booking, payment.booking_id)
        if booking:
            booking.status="requested"
            expert=db.get(Expert, booking.expert_id)
            customer=db.get(User, booking.user_id)
            join_path=f"/dashboard/booking-room.html?token={booking.meeting_token}"
            if expert and customer:
                db.add(Notification(user_id=customer.id, title="Booking requested", body=f"Payment verified. {expert.name} can now accept your booking."))
                join_link=f"{settings.FRONTEND_URL}{join_path}"
                body=(
                    f"Hi {customer.name},\n\n"
                    "Thank you for booking through OnCons. Your payment has been verified and your invoice is attached as a PDF.\n\n"
                    f"Consultant: {expert.name}\n"
                    f"Consultation category: {expert.category or 'Consultant'}\n"
                    f"Scheduled date/time: {booking.scheduled_at}\n"
                    f"Consultation mode: {(booking.mode or 'video').title()}\n"
                    f"Amount paid: INR {payment.amount}\n"
                    f"Direct meet link: {join_link}\n\n"
                    "The consultant will accept the request before the room opens. Keep this email for your demo/payment proof.\n\n"
                    "OnCons Team"
                )
                pdf=booking_bill_pdf(customer, expert, booking, payment, join_link)
                send_email_with_attachment(customer.email, "OnCons booking confirmation and tax invoice", body, f"oncons_invoice_{booking.id}", pdf)
                if expert.user_id:
                    expert_user=db.get(User, expert.user_id)
                    if expert_user:
                        notify_expert_booking(db, expert_user, customer, booking.scheduled_at, join_path)
            db.commit()
        return
    if desc.startswith("Call charge for booking #") and payment.booking_id:
        booking=db.get(Booking, payment.booking_id)
        if booking:
            booking.call_charge_status="paid"
            db.commit()
        return
    plan=desc.lower().split()[0]
    if plan not in ("pro","premium"):
        db.commit()
        return
    s=Subscription(user_id=payment.user_id, plan=plan, status="active",
                   renews_at=utcnow()+timedelta(days=30), provider=payment.provider, provider_ref=payment.provider_ref)
    db.add(s)
    u=db.get(User, payment.user_id); u.plan=plan
    db.commit()

def _issue_invoice(db, payment:Payment):
    existing=db.query(Invoice).filter_by(payment_id=payment.id).first()
    if existing:
        return existing
    invoice=Invoice(
        user_id=payment.user_id,
        booking_id=payment.booking_id,
        payment_id=payment.id,
        invoice_number=f"ONC-{utcnow().strftime('%Y%m%d')}-{payment.id:06d}",
        amount=payment.amount,
        currency=payment.currency or "INR",
        status="issued",
    )
    db.add(invoice)
    db.flush()
    return invoice
