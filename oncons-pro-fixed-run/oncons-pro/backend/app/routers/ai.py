from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, Expert, AIChat
from ..auth import current_user
from ..schemas import AIChatIn
from ..config import settings

router=APIRouter()

SYSTEM="""You are OnCons AI. Help the user describe their problem, classify the right expert category from this list:
Doctor, Psychiatrist, Therapist, Lawyer, Financial Advisor, Plumber, Mechanic, Electrician, Tutor,
Fitness Trainer, Nutritionist, Astrologer, Career Coach, Relationship Counselor, Interior Designer,
Architect, Freelance Consultant. Be empathetic and brief."""

CATS=["Doctor","Psychiatrist","Therapist","Lawyer","Financial Advisor","Plumber","Mechanic","Electrician","Tutor","Fitness Trainer","Nutritionist","Astrologer","Career Coach","Relationship Counselor","Interior Designer","Architect","Freelance Consultant"]

def _detect_category(text:str):
    t=text.lower()
    for c in CATS:
        if c.lower() in t: return c
    if any(w in t for w in ["sick","pain","doctor","fever","symptom","cough","injury","medicine"]): return "Doctor"
    if any(w in t for w in ["legal","contract","lawyer","court"]): return "Lawyer"
    if any(w in t for w in ["money","tax","invest","finance"]): return "Financial Advisor"
    if any(w in t for w in ["anxiety","depress","stress","therapy"]): return "Therapist"
    if any(w in t for w in ["tv","television","light","fan","switch","wiring","power","electric","current","socket"]): return "Electrician"
    if any(w in t for w in ["pipe","tap","water","leak","toilet","drain"]): return "Plumber"
    if any(w in t for w in ["car","bike","engine","brake","vehicle"]): return "Mechanic"
    if any(w in t for w in ["study","math","exam","homework","tuition"]): return "Tutor"
    if any(w in t for w in ["job","career","interview","resume"]): return "Career Coach"
    return None

def _fallback_reply(text:str, cat:str|None, urg:str):
    t=text.lower()
    tips=[]
    if cat=="Electrician":
        if "tv" in t:
            tips=["Check the power socket with another device.","Confirm the TV power cable is tight and the remote batteries work.","Try a 60 second power reset by unplugging the TV.","If there is burning smell, sparks, or repeated tripping, stop using it and book an electrician."]
        else:
            tips=["Turn off the affected switch or breaker first.","Avoid touching exposed wires.","Book an electrician if the issue repeats or there is heat, smell, or sparking."]
    elif cat=="Plumber":
        tips=["Close the nearest water valve if there is leakage.","Collect a photo/video of the issue for faster diagnosis.","Book a plumber if leakage continues or drainage is blocked."]
    elif cat=="Doctor":
        tips=["Track symptoms, temperature, medicines, and duration.","Seek urgent medical care for severe pain, breathing trouble, fainting, or heavy bleeding.","Book a doctor for a proper diagnosis."]
    elif cat=="Mechanic":
        tips=["Avoid driving if brakes, steering, smoke, or engine warnings are involved.","Note any sound, smell, or dashboard alert.","Book a mechanic with the vehicle model and issue details."]
    else:
        tips=["Share when the problem started, what you already tried, and any photos or documents.","I can help you choose the right consultant and prepare questions for the session."]
    follow={
        "Tutor":"Which subject, class/semester, and exact doubt should the tutor solve?",
        "Electrician":"Is there any spark, burning smell, or power trip, and what device is affected?",
        "Plumber":"Where is the leak/blockage and is the main valve closed?",
        "Lawyer":"What document/notice/dispute is involved and when is the deadline?",
        "Doctor":"How long have symptoms been present and are there any severe symptoms?",
    }.get(cat, "Share your location, urgency, and one photo/document if available.")
    return f"Best match: {cat or 'a suitable professional'}. Urgency: {urg}. " + " ".join(tips) + f" Next: {follow}"

def _urgency(text:str):
    t=text.lower()
    if any(w in t for w in ["urgent","emergency","asap","now","immediately"]): return "high"
    if any(w in t for w in ["soon","today","tomorrow"]): return "medium"
    return "low"

@router.post("/chat")
def chat(b:AIChatIn, u:User=Depends(current_user), db:Session=Depends(get_db)):
    user_msg=next((m["content"] for m in reversed(b.messages) if m.get("role")=="user"),"")
    cat=_detect_category(user_msg); urg=_urgency(user_msg)
    reply=None
    if settings.OPENAI_API_KEY:
        try:
            from openai import OpenAI
            client=OpenAI(api_key=settings.OPENAI_API_KEY)
            r=client.chat.completions.create(model="gpt-4o-mini",
                messages=[{"role":"system","content":SYSTEM}]+b.messages)
            reply=r.choices[0].message.content
        except Exception as e:
            reply=f"(AI offline) I'd suggest a {cat or 'professional'}. Urgency: {urg}."
    else:
        reply=_fallback_reply(user_msg, cat, urg)
    recs=[]
    if cat:
        for e in db.query(Expert).filter(Expert.category==cat, Expert.application_status=="approved", Expert.available==True).limit(3).all():
            recs.append({"id":e.id,"name":e.name,"fee":e.fee,"category":e.category,"rating":e.rating})
    db.add(AIChat(user_id=u.id, messages=b.messages+[{"role":"assistant","content":reply}]))
    db.commit()
    return {"reply":reply,"category":cat,"urgency":urg,"recommended_experts":recs}

@router.post("/summarize-reviews")
def summarize(payload:dict):
    # Stub: average sentiment summary
    texts=payload.get("reviews",[])
    return {"summary":"Most reviewers praise responsiveness and clarity." if texts else "No reviews to summarize."}
