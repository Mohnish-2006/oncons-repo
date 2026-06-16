from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Payment, Subscription, User, Booking, Expert, Notification
from ..auth import current_user
from ..schemas import CheckoutIn
from ..config import settings
from ..notifications import notify_expert_booking
from datetime import datetime, timedelta

router=APIRouter()
PLAN_AMOUNTS={"free":0,"pro":499,"premium":1499}
CALL_PACKAGES={1:5,5:25,10:35,15:99,20:99}

@router.post("/checkout")
def checkout(b:CheckoutIn, u:User=Depends(current_user), db:Session=Depends(get_db)):
    if b.purpose=="call_charge":
        booking=db.query(Booking).filter_by(id=b.booking_id,user_id=u.id).first()
        if not booking: raise HTTPException(404,"Booking not found")
        if u.plan=="premium":
            booking.call_charge_status="paid"
            db.commit()
            raise HTTPException(400,"Premium+ includes free video calls")
        minutes=b.call_minutes or booking.billable_minutes or 1
        if minutes not in CALL_PACKAGES:
            raise HTTPException(400,"Choose a valid call package")
        booking.billable_minutes=minutes
        db.commit()
        amt=CALL_PACKAGES[minutes]
        if amt <= 0: raise HTTPException(400,"No call charge due")
        desc=f"Call charge for booking #{booking.id} - {minutes} minutes"
    elif b.purpose=="details":
        expert=db.query(Expert).filter_by(id=b.expert_id, application_status="approved").first()
        if not expert: raise HTTPException(404,"Consultant not found")
        amt=settings.DETAILS_UNLOCK_AMOUNT
        desc=f"Details unlock for expertise {expert.category}"
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
    p.status="paid"
    p.provider_ref=payload.get("reference") or p.provider_ref
    db.commit()
    _activate_plan(db,p)
    return {"ok":True}

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
            booking.status="confirmed"
            expert=db.query(Expert).get(booking.expert_id)
            customer=db.query(User).get(booking.user_id)
            join_path=f"/dashboard/booking-room.html?token={booking.meeting_token}"
            if expert and customer:
                db.add(Notification(user_id=customer.id, title="Booking confirmed", body=f"Your appointment with {expert.name} is confirmed for {booking.scheduled_at}. Join here: {join_path}"))
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
    if desc.startswith("Details unlock for expert #"):
        # Details unlock payments are checked from paid payment records.
        return
    if desc.startswith("Details unlock for expertise "):
        return
    plan=desc.lower().split()[0]
    if plan not in ("pro","premium"): return
    s=Subscription(user_id=payment.user_id, plan=plan, status="active",
                   renews_at=datetime.utcnow()+timedelta(days=30), provider=payment.provider, provider_ref=payment.provider_ref)
    db.add(s)
    u=db.query(User).get(payment.user_id); u.plan=plan
    db.commit()
