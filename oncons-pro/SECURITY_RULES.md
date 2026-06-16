# Security Rules for OnCons Pro

## Required Rules
- Keep secrets only in `.env`; never put API keys or database URLs in frontend files.
- Keep `.env` out of git. Use `.env.example` for empty variable names.
- Rate limiting is enabled in `backend/app/main.py`: auth routes are stricter than general API routes.
- Validate all backend input with Pydantic schemas and ORM queries. Do not build raw SQL from user input.
- Admin routes must use explicit role checks.
- CORS must use `ALLOWED_ORIGINS`; do not use wildcard CORS in production.
- Security headers are set in `backend/app/main.py`.
- Do not render user content as raw HTML without sanitizing it first.
- Use real payment gateway webhooks for production payment verification.
- UPI QR/manual payment accepts only unique 12-digit UTRs, but bank-level verification requires Razorpay/Stripe/payment-provider webhook.
- SMTP credentials must stay in `.env`; expert booking emails are sent only after confirmed booking payment.
- Before deployment: run dependency audit, disable debug logging, enforce HTTPS, configure SMTP, configure payment webhooks, and use PostgreSQL.

## Production Payment Note
Manual UPI reference entry cannot prove bank settlement by itself. For genuine automatic verification, configure Razorpay/Stripe webhooks and verify provider signatures before marking a payment paid.
