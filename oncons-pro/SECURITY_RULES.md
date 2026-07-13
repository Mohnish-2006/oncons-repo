# Security Rules for OnCons Pro

## Required Rules
- Keep secrets only in `.env`; never put API keys or database URLs in frontend files.
- Keep `.env` out of git. Use `.env.example` for empty variable names.
- Rate limiting is enabled in `backend/app/main.py`: auth routes are stricter than general API routes.
- Validate all backend input with Pydantic schemas and ORM queries. Do not build raw SQL from user input.
- Admin routes must use explicit role checks.
- Login/register create server-side session records. Refresh tokens are hashed at rest and rotated through `/api/auth/refresh`.
- Use `/api/auth/logout` for current-device logout and `/api/auth/logout-all` to revoke all active sessions for a user.
- Registration passwords must be at least 10 characters and include uppercase, lowercase, number, and symbol.
- CORS must use `ALLOWED_ORIGINS`; do not use wildcard CORS in production.
- Security headers are set in `backend/app/main.py`.
- Do not render user content as raw HTML without sanitizing it first.
- Use real payment gateway webhooks for production payment verification.
- Set `ENVIRONMENT=production` before deployment. Production mode rejects demo payment methods and refuses unsafe SQLite/localhost/default-secret configuration.
- Razorpay payment confirmation must arrive through `/api/payments/razorpay/webhook`; the backend verifies `X-Razorpay-Signature` before marking a payment paid.
- Stripe payment confirmation must arrive through `/api/payments/stripe/webhook`; the backend verifies the Stripe signature before marking a payment paid.
- Refunds must be initiated by admins through the backend refund endpoint. The backend records refund transactions and uses provider APIs in production.
- Uploads must go through `/api/uploads`; Cloudinary credentials stay server-side and local uploads are only for development.
- UPI QR/manual payment accepts only unique 12-digit UTRs, but bank-level verification requires Razorpay/Stripe/payment-provider webhook.
- SMTP credentials must stay in `.env`; expert booking emails are sent only after confirmed booking payment.
- User complaints and reports are stored in backend tables and handled from admin pages. Do not collect support issues only in frontend text.
- GZip compression is enabled; public expert search uses bounded pagination.
- Before deployment: run dependency audit, disable debug logging, enforce HTTPS, configure SMTP, configure payment webhooks, and use PostgreSQL.

## Production Payment Note
Manual UPI reference entry cannot prove bank settlement by itself. For genuine automatic verification, configure Razorpay/Stripe webhooks and verify provider signatures before marking a payment paid.
