# Expert Booking Email Setup

Expert booking emails are already wired in the backend.

When a user pays and the booking becomes confirmed, the backend calls:

```text
backend/app/notifications.py -> notify_expert_booking(...)
```

To make real emails send, fill these values in:

```text
H:\oncons-pro-fixed-run\oncons-pro\backend\.env
```

Gmail example:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=your-email@gmail.com
```

Important:
- Use a Gmail App Password, not your normal Gmail password.
- The consultant must register with their real email.
- Email sends after the user's booking payment is accepted.
- If SMTP values are empty, the app still creates in-app notifications but cannot send email.
