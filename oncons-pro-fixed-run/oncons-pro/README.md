# OnCons Pro

Full-stack consultant booking website with static HTML/CSS/JS frontend, FastAPI backend, and SQL database support.

## What is included

- User registration and login.
- Consultant registration with OTP verification fields, profile photo, Aadhaar upload field, category, fee, city, languages, and bio.
- Consultant records are stored automatically in the database and shown on the public experts page.
- User dashboard does not show any consultant until the user books one.
- Booking creates a confirmed appointment, notifies the user and consultant, and generates a website room link.
- Website consultation room with chat, browser video call, and browser audio call controls.
- AI chatbot with better local NLP fallback for issues such as "my TV is not working", plumbing, legal, medical, finance, career, and repair problems.
- Subscription plans with more AI usage, review summaries, feedback, reports, priority booking, and support add-ons.
- UPI/QR payment path with environment settings for your own bank-linked UPI ID and QR code.
- SQLite for local testing, PostgreSQL recommended for real users.

## Run in VS Code

Open this folder in VS Code:

```powershell
C:\Users\harah\Documents\Codex\2026-05-20\files-mentioned-by-the-user-oncons\oncons-pro
```

Start backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python seed.py
uvicorn app.main:app --reload --port 8000
```

Start frontend in a second terminal:

```powershell
cd frontend
python -m http.server 5500
```

Open:

```text
http://localhost:5500
```

Default admin:

```text
admin@oncons.local
admin12345
```

Sample expert password:

```text
expert123
```

## Payment QR setup

Edit `backend/.env`:

```env
UPI_ID=your-upi-id@bank
UPI_PAYEE_NAME=Your Business Name
PAYMENT_QR_URL=https://your-domain.com/your-qr.png
```

Your QR image must be hosted somewhere public, or placed in your frontend assets and referenced by URL. The bank account receiving the money is controlled by the UPI ID or QR code you provide.

For real payments, use Razorpay/Stripe webhooks and verify signatures before marking payments as paid.

## Best database for real people

Use PostgreSQL for production. Good options are Supabase Postgres, Neon, Railway Postgres, or Render Postgres.

Set this in `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@host:5432/oncons
```

SQLite is only for local development.

## Production notes

- Replace local OTP return with SMS/email delivery before launch.
- Store Aadhaar/profile uploads in Cloudinary/S3 instead of database data URLs.
- Use HTTPS for camera and microphone on deployed sites.
- Add WebRTC signaling or a video provider such as Agora, Twilio, Daily, or Jitsi for real two-person video rooms.
- Verify Razorpay/Stripe webhooks before activating subscriptions.
