# OnCons - Online Consultation and Expert Booking Platform

OnCons is a full-stack consultation marketplace where learners/customers can find experts, pay to unlock extra expert details, book a consultation, and join a video/audio/chat room. Consultants register with email OTP verification, upload certificate proof for professional domains, manage their profile, accept or reject bookings, and track earnings, reviews, and notifications.

## Problem Statement

Students, service providers, and customers often need quick expert help but do not have a simple local-demo friendly platform for discovery, booking, payment, verification, and consultation in one flow. OnCons solves this by combining authentication, role-based dashboards, OTP verification, payment simulation, booking management, notifications, recommendations, profile management, and Jitsi Meet consultation rooms.

## Simple Explanation

A user registers, browses consultants, pays INR 25 to unlock extra consultant details when needed, selects date/time/mode, pays to confirm the booking, and joins the consultation room. A consultant registers separately, verifies email OTP, uploads certificate proof if the domain needs it, manages profile and availability, accepts or rejects bookings, joins the same room, and checks earnings/reviews.

## Technical Explanation

The frontend is built with HTML, CSS, and JavaScript. The backend is built with FastAPI, SQLAlchemy, SQLite/PostgreSQL, JWT authentication, SMTP email OTP, Razorpay payment verification, and Jitsi Meet iframe rooms. SQLite keeps the demo easy to run on a student laptop, while PostgreSQL plus Razorpay webhooks are ready for hosting.

## Tech Stack

- Frontend: HTML, CSS, JavaScript, responsive UI
- Backend: Python, FastAPI, SQLAlchemy
- Database: SQLite for local demo
- Auth: JWT tokens, password hashing
- OTP: Gmail SMTP with app password
- Payments: Razorpay checkout with backend signature/webhook verification; UPI/card demo methods for local development
- Video: Jitsi Meet iframe
- Recommendation: keyword/category/rating/availability matching, optional OpenAI fallback

This stack is suitable for a student project because it is lightweight, easy to run locally, clear to explain in viva/interview, and still demonstrates real full-stack concepts.

## Architecture

```text
Browser
  |
  | HTML/CSS/JS frontend
  v
FastAPI backend
  |
  | SQLAlchemy ORM
  v
SQLite database

External:
Gmail SMTP -> OTP email
Razorpay -> payment checkout and verified webhooks
Jitsi Meet -> video call room
```

## User Workflow

`register/login -> browse experts -> view expert -> pay INR 25 for extra details -> choose date/time/mode -> pay and confirm booking -> booking dashboard -> join video/call/chat -> review`

User dashboard stays user-focused: overview, bookings, profile, notifications, upcoming consultant, account plan/status, total spent, and recent notifications.

## Consultant/Admin Workflow

`register as consultant -> email OTP -> certificate proof if required -> verification success -> dashboard -> manage profile -> view upcoming requests -> accept/reject -> join consultation -> earnings/reviews`

Consultant dashboard is separate from the user dashboard: dashboard, upcoming, earnings, availability, profile, notifications, reviews, accept/reject actions, certificate/portfolio/profile fields.

## Certificate Proof Logic

Certificate proof is required for:

Doctor, Psychiatrist, Therapist, Lawyer, Financial Advisor, Nutritionist, Interior Designer, Architect.

Certificate proof is not required for:

Tutor, Plumber, Mechanic, Electrician, Fitness Trainer, Career Coach, Relationship Counselor, Astrologer, Freelance Consultant, and general informal service categories.

The frontend shows/hides the upload field, and the backend validates the same rule before account creation.

## Payment Flow

Payment places:

- INR 25 paid expert details unlock
- Booking payment before booking appears in user dashboard
- Extra call minutes when required

Hosted payments use Razorpay checkout. The frontend opens Razorpay, then the backend verifies the signed callback at `/api/payments/razorpay/verify`. In production, Razorpay also calls `/api/payments/razorpay/webhook`, and the backend verifies `X-Razorpay-Signature` before marking a payment paid.

Local development still supports UPI QR, debit card demo, and credit card demo from selected screens. Demo methods are blocked automatically when `ENVIRONMENT=production`.

## Backend Modules

- `auth.py`: JWT, passwords, current user helpers
- `routers/auth.py`: user registration, login, OTP send, consultant registration
- `routers/experts.py`: expert listing, detail, paid details, reviews
- `routers/bookings.py`: booking creation
- `routers/payments.py`: checkout, Razorpay signature verification, Razorpay/Stripe webhooks, refunds, status polling
- `routers/me.py`: user profile, bookings, payments, notifications, room, messages
- `routers/expert_portal.py`: consultant dashboard, profile, bookings, earnings, availability
- `routers/ai.py`: recommendation/matching assistant
- `models.py`: SQLAlchemy database tables
- `schemas.py`: request/response validation
- `notifications.py`: email and in-app notifications

## Database Tables

`users`, `experts`, `bookings`, `payments`, `notifications`, `reviews`, `messages`, `otp_verifications`, `subscriptions`, plus supporting tables such as categories, availability, transactions, AI chats, support tickets, and admin logs.

## Folder Structure

```text
oncons-pro/
  backend/
    app/
      routers/
      models.py
      schemas.py
      config.py
      main.py
      auth.py
      db.py
      notifications.py
    requirements.txt
    .env
    .env.example
    seed.py
    oncons.db

  frontend/
    index.html
    register.html
    login.html
    expert-detail.html
    experts.html
    pricing.html
    dashboard/
    expert/
    admin/
    assets/
      css/
      js/
      img/
```

## Important API Endpoints

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/otp/send`
- `POST /api/auth/consultant/register`
- `GET /api/experts`
- `GET /api/experts/{id}`
- `GET /api/experts/{id}/paid-details`
- `POST /api/bookings`
- `POST /api/payments/checkout`
- `POST /api/payments/razorpay/verify`
- `POST /api/payments/razorpay/webhook`
- `GET /api/payments/{id}/status`
- `GET /api/me/bookings`
- `GET /api/me/notifications`
- `GET /api/me/booking-room/{token}`
- `POST /api/expert/bookings/{id}/decision`
- `GET /api/expert/summary`
- `PATCH /api/expert/me`
- `POST /api/ai/chat`

## OTP Email Setup

Create `backend/.env` from `backend/.env.example` and configure Gmail SMTP. OTP is required for both user registration and consultant registration:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=oncons.business@gmail.com
SMTP_PASSWORD=GOOGLE_APP_PASSWORD
FROM_EMAIL=oncons.business@gmail.com
OTP_REQUIRE_EMAIL_DELIVERY=true
```

Use a Gmail App Password, not the normal Gmail password. Never commit `.env`.

## How To Run

Backend:

```powershell
cd H:\oncons-pro-fixed-run\oncons-pro-fixed-run\oncons-pro\backend
.\.venv312\Scripts\python.exe seed.py
.\.venv312\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd H:\oncons-pro-fixed-run\oncons-pro-fixed-run\oncons-pro\frontend
py -m http.server 5500 --bind 0.0.0.0
```

Open:

```text
http://localhost:5500/index.html
```

Local admin login:

```text
URL: http://localhost:5500/login.html?role=admin
Email: admin@oncons.com
Password: Admin@12345
```

For hosting, set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` in Render. Set the Razorpay webhook URL to:

```text
https://YOUR-RENDER-API.onrender.com/api/payments/razorpay/webhook
```

Two laptops:

1. Connect both laptops to the same Wi-Fi or phone hotspot.
2. Run backend/frontend on the main laptop.
3. Find the main laptop IP using `ipconfig`.
4. On the second laptop open `http://MAIN-LAPTOP-IP:5500/index.html`.

## Testing Checklist

User:

- Register user
- Login user
- Browse experts
- Pay INR 25 for details
- Verify payment wait screen
- Book consultation with date/time/mode
- Pay using UPI QR
- Pay using debit card form
- Pay using credit card form
- See booking in dashboard
- Join consultation room
- Update profile photo

Consultant:

- Register as consultant/admin
- Send OTP to email
- Enter OTP
- Upload certificate for required domain
- See green tick confirmation page
- Redirect to consultant dashboard
- Edit consultant profile/photo/portfolio
- See booking request
- Accept booking
- Reject booking
- Join consultation room
- View earnings/reviews

## Implementation Phases

1. Inspect current app: reviewed existing backend/frontend and the reference zip layout.
2. Fix auth and OTP: consultant OTP registration uses SMTP and stops if required delivery fails.
3. Separate dashboards: user dashboard and consultant dashboard are different pages with different sidebars.
4. Add certificate proof logic: frontend and backend both enforce professional-domain proof.
5. Add booking date/time/mode: booking stores selected consultation mode.
6. Add QR/card payment UI: UPI QR, debit card, and credit card options are available.
7. Add backend verification: payment status auto-verifies for classroom demo.
8. Add INR 25 details: paid details stay locked until payment is verified.
9. Add accept/reject booking: consultant can accept or reject paid booking requests.
10. Add profiles/photos: user and consultant profiles persist in the database.
11. Add video room notifications: joining call creates simple notifications.
12. Test full demo flow: run backend import checks and browser demo checks.
13. Write README and GitHub docs: this file explains setup, testing, limitations, and viva answers.

Common mistakes: using normal Gmail password instead of app password, committing `.env`, opening the second laptop with `localhost` instead of main laptop IP, expecting static UPI QR to verify real bank payment, and mixing user dashboard pages with consultant dashboard pages.

## Screenshots To Capture

Home page, user register/login, user dashboard, expert listing, expert detail page, INR 25 details payment, UPI QR screen, debit/credit card form, booking form, user bookings, user profile, consultation room, consultant registration with certificate proof, OTP email, green tick success, consultant dashboard, accept/reject bookings, consultant profile, earnings, notifications, SQLite database, API testing, GitHub repository.

## GitHub Proof Strategy

Suggested commit plan:

- Day 1: Initial project setup
- Day 2: Authentication and OTP
- Day 3: User dashboard and expert listing
- Day 4: Admin/consultant dashboard separation
- Day 5: Booking and payment flow
- Day 6: Video call and notifications
- Day 7: Profile, certificate proof, and reviews
- Day 8: README, screenshots, and final polish

Suggested commit messages:

- `feat: add user authentication and OTP verification`
- `feat: separate user and admin dashboards`
- `feat: add expert booking and payment flow`
- `feat: add certificate proof validation`
- `feat: add video consultation room`
- `feat: add profile photos and portfolio`
- `docs: add complete README and demo steps`

## Interview Preparation

Strong answer:

"OnCons is a full-stack expert consultation platform where users can browse verified consultants, pay to unlock additional details, book consultations, and join video/audio/chat sessions. Consultants register through email OTP, upload certificate proof if their domain requires it, manage their profile, accept or reject bookings, and track earnings and reviews. The backend is built with FastAPI, SQLAlchemy, JWT authentication, SMTP OTP, payment verification flow, and SQLite. The frontend is built with HTML, CSS, and JavaScript. The project demonstrates authentication, role-based dashboards, database design, payment flow, video-call integration, profile management, and real-world service marketplace logic."

Good viva points:

- User and consultant dashboards are separate because each role has different goals.
- OTP verification uses SMTP email and an expiry-limited OTP table.
- Certificate proof is category-based and checked on frontend and backend.
- Booking becomes visible only after payment status is verified.
- Static UPI QR payment is simulated for demo; production needs payment gateway webhook.
- Video calling uses a shared Jitsi room token so both laptops join the same room.
- The project demonstrates full-stack CRUD, auth, payments, notifications, recommendation logic, and database design.
# Oncons
