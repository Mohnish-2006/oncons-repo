from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Payment, Subscription, User, Booking, Expert, Notification
from ..auth import current_user
from ..schemas import CheckoutIn
from ..config import settings
from ..notifications import notify_expert_booking, send_email_with_attachment
from ..billing import booking_bill_pdf
from datetime import datetime, timedelta
import re

router=APIRouter()
PLAN_AMOUNTS={"free":0,"pro":499,"premium":1499}
CALL_PACKAGES={10:49,15:69,30:129}

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
        expert=db.query(Expert).get(b.expert_id)
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
        try:
            import razorpay
            client=razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order=client.order.create({"amount":int(amt*100),"currency":"INR","receipt":f"pmt_{p.id}"})
            p.provider_ref=order["id"]; db.commit()
            return {"checkout_url":f"https://checkout.razorpay.com/v1/checkout.html?order_id={order['id']}","order_id":order['id'],"key":settings.RAZORPAY_KEY_ID}
        except Exception as e:
            return {"checkout_url":f"https://stub.local/razorpay/{p.id}","note":str(e)}
    if b.provider=="stripe":
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
            return {"checkout_url":f"https://stub.local/stripe/{p.id}","note":str(e)}
    raise HTTPException(400,"Unknown provider")

@router.post("/{pid}/mark-paid")
def mark_paid(pid:int, payload:dict, u:User=Depends(current_user), db:Session=Depends(get_db)):
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
    age=(datetime.utcnow()-p.created_at).total_seconds()
    if p.provider in ("upi", "debit_card", "credit_card") and p.status=="initiated" and age>=8:
        p.status="paid"
        p.provider_ref=p.provider_ref or f"AUTO-{p.id}"
        db.commit()
        _activate_plan(db,p)
    return {"id":p.id,"status":p.status,"amount":p.amount,"description":p.description}

@router.post("/razorpay/webhook")
async def rzp_webhook(req:Request, db:Session=Depends(get_db)):
    body=await req.json()
    # TODO: verify X-Razorpay-Signature
    pid=body.get("payload",{}).get("payment",{}).get("entity",{}).get("notes",{}).get("payment_id")
    if pid:
        p=db.query(Payment).get(int(pid)); p.status="paid"; db.commit()
        _activate_plan(db,p)
    return {"ok":True}

@router.post("/stripe/webhook")
async def stripe_webhook(req:Request, db:Session=Depends(get_db)):
    # TODO: stripe.Webhook.construct_event
    return {"ok":True}

def _activate_plan(db, payment:Payment):
    desc=payment.description or ""
    if desc.startswith("Consultation booking #") and payment.booking_id:
        booking=db.query(Booking).get(payment.booking_id)
        if booking:
            booking.status="requested"
            expert=db.query(Expert).get(booking.expert_id)
            customer=db.query(User).get(booking.user_id)
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
                    expert_user=db.query(User).get(expert.user_id)
                    if expert_user:
                        notify_expert_booking(db, expert_user, customer, booking.scheduled_at, join_path)
            db.commit()
        return
    if desc.startswith("Call charge for booking #") and payment.booking_id:
        booking=db.query(Booking).get(payment.booking_id)
        if booking:
            booking.call_charge_status="paid"
            db.commit()
        return
    plan=desc.lower().split()[0]
    if plan not in ("pro","premium"): return
    s=Subscription(user_id=payment.user_id, plan=plan, status="active",
                   renews_at=datetime.utcnow()+timedelta(days=30), provider=payment.provider, provider_ref=payment.provider_ref)
    db.add(s)
    u=db.query(User).get(payment.user_id); u.plan=plan
    db.commit()
