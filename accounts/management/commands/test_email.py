import os
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from dotenv import load_dotenv

load_dotenv(override=True)


class Command(BaseCommand):
    help = "Test email sending connection and send a test OTP email to a specified recipient."

    def add_arguments(self, parser):
        parser.add_argument("recipient", type=str, help="Recipient email address to test delivery")

    def handle(self, *args, **options):
        recipient = options["recipient"]
        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(self.style.NOTICE("[TEST] Testing Email Delivery Configuration"))
        self.stdout.write(self.style.NOTICE("=" * 60))

        host_user = os.getenv("EMAIL_HOST_USER", "").strip()
        host_pw = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
        is_configured = getattr(settings, "IS_SMTP_CONFIGURED", False)

        self.stdout.write(f"EMAIL_HOST_USER: {host_user or '(not set)'}")
        self.stdout.write(f"EMAIL_HOST_PASSWORD: {'*' * len(host_pw) if host_pw else '(not set)'}")
        self.stdout.write(f"Live SMTP Mode Active: {is_configured}")
        self.stdout.write("-" * 60)

        if not is_configured:
            self.stdout.write(self.style.WARNING("[NOTICE] Real Gmail SMTP is not yet active because your credentials in .env are still placeholders."))
            self.stdout.write(self.style.WARNING("To send real emails to inboxes, edit d:\\SIH\\CODE\\.env with your Gmail & 16-character App Password."))
            self.stdout.write(self.style.NOTICE("Running in Console / Dev Mode instead...\n"))

        self.stdout.write(f"Sending test email to: {recipient}...")

        try:
            sent_count = send_mail(
                subject="Test Verification Code - Lost & Found System",
                message=(
                    f"Hello,\n\n"
                    f"This is a test email from your Lost & Found platform.\n"
                    f"Test OTP Code: 123456\n\n"
                    f"If you received this in your inbox, your email configuration is 100% working!"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            if is_configured:
                self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Email dispatched to {recipient} via Gmail SMTP."))
            else:
                self.stdout.write(self.style.SUCCESS(f"[OK] Console email generated successfully! (Add real credentials to .env to deliver to real inbox)."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAILED] Could not send email: {e}"))
            error_str = str(e)
            if "535" in error_str or "BadCredentials" in error_str:
                self.stdout.write(self.style.WARNING(
                    "\n[FIX FOR GMAIL 535 ERROR]:\n"
                    "1. Make sure you are using a 16-character 'Google App Password', NOT your standard Gmail password.\n"
                    "2. Enable 2-Step Verification on your Google Account: https://myaccount.google.com/security\n"
                    "3. Generate an App Password at: https://myaccount.google.com/apppasswords\n"
                    "4. Paste it into d:\\SIH\\CODE\\.env under EMAIL_HOST_PASSWORD without spaces."
                ))
            elif "ConnectionRefused" in error_str or "timed out" in error_str:
                self.stdout.write(self.style.WARNING(
                    "\n[FIX]: Could not reach smtp.gmail.com:587. Check your internet connection or firewall."
                ))
