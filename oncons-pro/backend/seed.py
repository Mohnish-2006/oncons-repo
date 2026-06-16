# Seeds categories, sample experts, and an admin user.
# Run: python seed.py
from app.db import Base, engine, SessionLocal
from app.models import Category, User, Expert
from app.auth import hash_pw

Base.metadata.create_all(bind=engine)
db=SessionLocal()

CATS=[
    ("Doctor","medical"),("Psychiatrist","mental-health"),("Therapist","therapy"),("Lawyer","legal"),
    ("Financial Advisor","finance"),("Plumber","plumbing"),("Mechanic","mechanic"),("Electrician","electric"),
    ("Tutor","education"),("Fitness Trainer","fitness"),("Nutritionist","nutrition"),("Astrologer","astrology"),
    ("Career Coach","career"),("Relationship Counselor","relationship"),("Interior Designer","interior"),
    ("Architect","architecture"),("Freelance Consultant","freelance")
]

for name, icon in CATS:
    if not db.query(Category).filter_by(name=name).first():
        db.add(Category(name=name, icon=icon))

if not db.query(User).filter_by(email="admin@oncons.local").first():
    db.add(User(name="Admin", email="admin@oncons.local", password_hash=hash_pw("admin12345"), role="admin"))

SAMPLES=[
    ("Dr. Priya Sharma","Doctor",14,1200,4.9,"Senior doctor for everyday health guidance and second opinions.","Mumbai","English, Hindi"),
    ("Adv. Rahul Mehra","Lawyer",9,2500,4.8,"Corporate and civil lawyer for contracts, notices, and disputes.","Delhi","English, Hindi"),
    ("CA Neha Verma","Financial Advisor",11,900,4.6,"Tax planning, investments, and personal finance consultant.","Bengaluru","English, Hindi"),
    ("Amit Rao","Electrician",8,499,4.7,"Home electrical repairs including TV power issues, wiring, switches, and safety checks.","Pune","Hindi, Marathi"),
    ("Ramesh Iyer","Plumber",12,399,4.7,"Leakage, tap, drainage, and bathroom repair specialist.","Chennai","English, Tamil"),
]

for name, category, years, fee, rating, bio, city, languages in SAMPLES:
    if not db.query(Expert).filter_by(name=name).first():
        email=name.lower().replace(" ",".").replace("adv.","adv").replace("dr.","dr")+"@oncons.local"
        user=User(name=name, email=email, password_hash=hash_pw("expert123"), role="expert")
        db.add(user); db.flush()
        db.add(Expert(user_id=user.id, name=name, category=category, years_experience=years,
                      fee=fee, rating=rating, bio=bio, city=city, languages=languages,
                      verified=True, application_status="approved", available=True))

db.commit()
print("Seeded OnCons Pro.")
