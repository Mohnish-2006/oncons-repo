# OnCons Production Deployment

## Targets

- Frontend: Cloudflare Pages, serving `frontend/`.
- Backend: Render web service, serving `backend/`.
- Database: Neon PostgreSQL.
- Email: Resend, Brevo, or SMTP-compatible provider.
- Payments: Razorpay with verified webhooks.
- Storage: Cloudinary for uploaded images/documents.

## Backend Environment

Set these on Render:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql://USER:PASSWORD@HOST/oncons?sslmode=require
JWT_SECRET=replace-with-a-long-random-secret
JWT_EXP_MIN=60
REFRESH_TOKEN_DAYS=30
FRONTEND_URL=https://your-cloudflare-pages-domain
ALLOWED_ORIGINS=https://your-cloudflare-pages-domain
RAZORPAY_KEY_ID=rzp_live_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASSWORD=xxx
FROM_EMAIL=OnCons <noreply@yourdomain.com>
CLOUDINARY_URL=cloudinary://...
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=8
```

Production startup rejects SQLite, localhost origins, default JWT secrets, and non-HTTPS frontend URLs.

## Database

Run migrations during deploy:

```powershell
cd backend
alembic upgrade head
```

Render uses this in `render.yaml` automatically.

## Razorpay Webhook

Configure the Razorpay dashboard webhook URL:

```text
https://your-render-api.onrender.com/api/payments/razorpay/webhook
```

Set a webhook secret in Razorpay, copy it to `RAZORPAY_WEBHOOK_SECRET`, and subscribe to payment captured/authorized events. The backend verifies `X-Razorpay-Signature` before marking any payment paid.

## Stripe Webhook

Configure the Stripe dashboard webhook URL:

```text
https://your-render-api.onrender.com/api/payments/stripe/webhook
```

Set `STRIPE_WEBHOOK_SECRET` from Stripe. The backend verifies the Stripe signature before marking a payment paid.

## Uploads

Set `CLOUDINARY_URL` in Render. The frontend sends files to `/api/uploads`; the backend uploads to Cloudinary and returns a secure URL. Local file uploads are development-only.

## Cloudflare Pages

Deploy the `frontend/` folder. Set the API URL in `frontend/assets/js/config.js` if the backend is on a different domain:

```js
window.ONCONS_API = "https://your-render-api.onrender.com/api";
```

## Health Checks

- Public backend health: `/health`
- Admin platform health: `/api/admin/platform-health`

## Pre-Launch Checklist

- `ENVIRONMENT=production`
- Neon PostgreSQL connected and migrated
- Cloudflare URL in `FRONTEND_URL` and `ALLOWED_ORIGINS`
- Razorpay live keys and webhook configured
- SMTP provider configured
- Cloudinary configured
- No `.env`, SQLite DB, virtualenv, or cache files committed
- Run backend tests before deploy
