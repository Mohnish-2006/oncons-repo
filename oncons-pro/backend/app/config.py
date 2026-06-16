from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./oncons.db"
    JWT_SECRET: str = "dev-secret"
    JWT_ALGO: str = "HS256"
    JWT_EXP_MIN: int = 60
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"
    OPENAI_API_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    CLOUDINARY_URL: str = ""
    FRONTEND_URL: str = "http://localhost:5500"
    ALLOWED_ORIGINS: str = "http://localhost:5500,http://localhost:5600,http://127.0.0.1:5500,http://127.0.0.1:5600"
    UPI_ID: str = ""
    UPI_PAYEE_NAME: str = "OnCons"
    PAYMENT_QR_URL: str = ""
    OTP_REQUIRE_EMAIL_DELIVERY: bool = False
    UPLOAD_DIR: str = "uploads"
    CALL_FREE_MINUTES: int = 5
    CALL_RATE_PER_MINUTE: int = 25
    DETAILS_UNLOCK_AMOUNT: int = 25
    UPI_UTR_REGEX: str = r"^\d{12}$"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    SMS_WEBHOOK_URL: str = ""
    class Config:
        env_file = ".env"
settings = Settings()
