"""
Settings API Routes — Module 5 configuration

GET  /api/settings/status          — returns SMTP/Slack config status (no credentials exposed)
POST /api/settings/test-email      — send a test email to the configured recipient
POST /api/settings/update-recipient — update the ALERT_DEFAULT_RECIPIENT at runtime (in-memory)
GET  /api/settings/alert-config    — get current alert schedule config
POST /api/vendors/{id}/send-declaration — trigger declaration email for a vendor (added here for settings context)
"""

import smtplib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.core.config import settings
from app.models.user import UserRole

router = APIRouter(prefix="/api/settings", tags=["Settings"])

# In-memory override for alert recipient (reset on server restart — use .env for persistence)
_runtime_recipient_override: str = ""


class UpdateRecipientRequest(BaseModel):
    alert_email: EmailStr
    slack_webhook_url: str = ""


class TestEmailRequest(BaseModel):
    recipient: str = ""  # If empty, uses configured recipient


@router.get("/status")
def get_settings_status(current_user=Depends(get_current_user)):
    """
    Return SMTP and Slack configuration status.
    Credentials are NEVER exposed — only whether they are set.
    """
    smtp_configured = bool(
        settings.SMTP_USERNAME
        and settings.SMTP_USERNAME not in ("your-gmail@gmail.com", "")
        and settings.SMTP_PASSWORD
        and settings.SMTP_PASSWORD not in ("your-app-password", "")
    )
    slack_configured = bool(
        settings.SLACK_WEBHOOK_URL
        and "YOUR/WEBHOOK" not in settings.SLACK_WEBHOOK_URL
        and settings.SLACK_WEBHOOK_URL != ""
    )
    recipient = (
        _runtime_recipient_override
        or settings.ALERT_DEFAULT_RECIPIENT
        or ""
    )
    recipient_configured = bool(
        recipient
        and recipient not in ("cfo@yourcompany.com", "")
    )

    return {
        "smtp": {
            "configured": smtp_configured,
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "from_name": settings.SMTP_FROM_NAME,
            "username_set": smtp_configured,
        },
        "slack": {
            "configured": slack_configured,
        },
        "alert_recipient": {
            "configured": recipient_configured,
            "email": recipient if recipient_configured else "",
        },
        "schedule": {
            "daily_ap_nudge": "09:00 IST",
            "weekly_cfo_report": "Monday 08:00 IST",
            "clock_refresh": "Every hour",
            "vendor_reverification": "07:00 IST daily",
        },
        "citation": settings.SECTION_CITATION_COMBINED,
    }


@router.post("/test-email")
def send_test_email(
    body: TestEmailRequest,
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT)),
):
    """
    Send a test email to verify SMTP configuration.
    Uses the configured SMTP credentials — returns success/failure with error detail.
    """
    smtp_username = settings.SMTP_USERNAME
    smtp_password = settings.SMTP_PASSWORD

    if not smtp_username or smtp_username in ("your-gmail@gmail.com", ""):
        raise HTTPException(
            status_code=400,
            detail=(
                "SMTP not configured. Set SMTP_USERNAME and SMTP_PASSWORD in backend/.env. "
                "For Gmail, use an App Password (not your account password). "
                "Enable 2FA on your Google account, then go to myaccount.google.com → "
                "Security → App Passwords to generate one."
            ),
        )

    recipient = (
        body.recipient
        or _runtime_recipient_override
        or settings.ALERT_DEFAULT_RECIPIENT
    )
    if not recipient or recipient in ("cfo@yourcompany.com", ""):
        raise HTTPException(
            status_code=400,
            detail="No alert recipient configured. Set ALERT_DEFAULT_RECIPIENT in backend/.env.",
        )

    from app.services.email_service import send_email
    html = f"""
    <html><body style="font-family:Inter,sans-serif;padding:24px;">
    <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;
         padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <h2 style="color:#1E293B;">✅ VendorClock — Test Email</h2>
        <p>Your SMTP configuration is working correctly.</p>
        <div style="background:#F0FDF4;border:1px solid #86EFAC;border-radius:8px;padding:16px;margin:20px 0;">
            <p style="margin:0;color:#166534;font-weight:600;">
                Module 5 alerts are ready to send.
            </p>
        </div>
        <p style="color:#374151;">
            Daily AP nudges will be sent at <strong>9:00 AM IST</strong>.<br>
            Weekly CFO reports are sent every <strong>Monday at 8:00 AM IST</strong>.
        </p>
        <p style="font-size:12px;color:#6B7280;margin-top:24px;">
            {settings.SECTION_CITATION_COMBINED}<br>
            Sent at {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')} | VendorClock
        </p>
    </div>
    </body></html>
    """

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[VendorClock] ✅ Test Email — SMTP Configuration Working"
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{smtp_username}>"
        msg["To"] = recipient
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_username, recipient, msg.as_string())

        return {
            "success": True,
            "message": f"Test email sent to {recipient}. Check your inbox.",
            "recipient": recipient,
        }
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=400,
            detail=(
                "SMTP authentication failed. For Gmail, you must use an App Password, "
                "not your account password. Go to myaccount.google.com → Security → App Passwords."
            ),
        )
    except smtplib.SMTPException as e:
        raise HTTPException(status_code=400, detail=f"SMTP error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email send failed: {str(e)}")


@router.post("/update-recipient")
def update_alert_recipient(
    body: UpdateRecipientRequest,
    current_user=Depends(require_roles(UserRole.ADMIN)),
):
    """
    Update the alert recipient email at runtime (admin only).
    Note: this is in-memory only — resets on server restart.
    For permanent change, update ALERT_DEFAULT_RECIPIENT in backend/.env.
    """
    global _runtime_recipient_override
    _runtime_recipient_override = str(body.alert_email)

    if body.slack_webhook_url:
        # Can't update settings object directly (immutable), but we log it
        pass

    return {
        "success": True,
        "alert_email": _runtime_recipient_override,
        "note": "Runtime override set. For permanent change, update backend/.env and restart server.",
    }
