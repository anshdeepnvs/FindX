import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp_email(user, otp_code):
    """
    Sends a beautifully formatted OTP email with plain text and HTML versions.
    Returns (success: bool, info_message: str)
    """
    subject = f"Your Verification Code: {otp_code} - Lost & Found Portal"

    text_content = (
        f"Hello {user.username},\n\n"
        f"Thank you for signing up with the Anti-Scam Lost & Found System.\n\n"
        f"Your 6-digit email verification code is: {otp_code}\n\n"
        f"This code will expire in 10 minutes.\n"
        f"Security Notice: Never share this OTP with anyone.\n\n"
        f"Stay safe,\n"
        f"The Lost & Found Team"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 30px 16px; color: #1e293b;">
      <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        
        <div style="margin-bottom: 24px; text-align: center;">
          <h2 style="margin: 0; font-size: 22px; color: #0f172a; font-weight: 800;">
            🔍 Lost & Found Portal
          </h2>
          <span style="display: inline-block; margin-top: 6px; background: #eff6ff; color: #2563eb; font-size: 11px; padding: 4px 10px; border-radius: 999px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border: 1px solid #bfdbfe;">
            🛡️ Anti-Scam Protection
          </span>
        </div>

        <p style="font-size: 15px; line-height: 1.6; color: #334155; margin-bottom: 16px;">
          Hello <strong>{user.username}</strong>,
        </p>
        <p style="font-size: 14px; line-height: 1.6; color: #64748b; margin-bottom: 24px;">
          Please enter the 6-digit one-time code below to verify your email address and activate your anti-scam protection:
        </p>
        
        <div style="background: #f1f5f9; border: 2px dashed #2563eb; border-radius: 10px; text-align: center; padding: 20px 12px; margin: 20px 0;">
          <div style="font-size: 11px; font-weight: 700; color: #2563eb; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
            Your Verification Code
          </div>
          <div style="font-size: 38px; font-weight: 900; letter-spacing: 8px; color: #1e40af;">
            {otp_code}
          </div>
          <div style="font-size: 12px; color: #64748b; margin-top: 8px;">
            ⏱️ Valid for 10 minutes only
          </div>
        </div>

        <div style="background: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 14px; font-size: 13px; color: #92400e; border-radius: 4px; margin: 24px 0;">
          <strong>🔒 Security Tip:</strong> Never share this code with anyone. Representatives will never call or ask you for your verification code.
        </div>

        <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;">

        <div style="text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5;">
          If you did not request this email, you can safely ignore it.<br>
          &copy; Lost & Found Community Network.
        </div>
      </div>
    </body>
    </html>
    """

    if not user or not getattr(user, "email", None) or not user.email.strip():
        logger.warning(f"send_otp_email called with invalid recipient: {user}")
        return False, "No recipient email address provided."

    try:
        send_mail(
            subject=subject,
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email.strip()],
            html_message=html_content,
            fail_silently=False,
        )
        return True, "Email dispatched successfully."
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error sending email to {user.email}: {err_msg}")
        if "535" in err_msg or "BadCredentials" in err_msg:
            friendly_err = "Gmail authentication failed (Bad Credentials). Make sure 2-Step Verification is ON and you generated a 16-character Google App Password from https://myaccount.google.com/apppasswords."
        elif "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            friendly_err = "SMTP connection timed out. The mail server could not be reached in 10 seconds."
        elif "connection refused" in err_msg.lower():
            friendly_err = "SMTP connection refused. Port 587 may be blocked or unreachable."
        else:
            friendly_err = err_msg
        return False, friendly_err
