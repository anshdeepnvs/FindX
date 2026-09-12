"""
email_backends.py — Custom, resilient email backends for FindX.

Provides ResendEmailBackend which sends emails via Resend's HTTPS REST API
(Port 443), completely bypassing SMTP port blocks on Render / cloud free tiers.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """
    Sends emails using Resend REST API (https://api.resend.com/emails) over HTTPS port 443.
    Requires RESEND_API_KEY in settings or environment.
    """

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = (api_key or os.getenv("RESEND_API_KEY", "")).strip()

    def send_messages(self, email_messages):
        if not email_messages or not self.api_key:
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                html_body = ""
                # Check for alternatives (HTML content)
                for alt_content, alt_mimetype in getattr(message, "alternatives", []):
                    if alt_mimetype == "text/html":
                        html_body = alt_content
                        break

                sender = message.from_email or os.getenv("DEFAULT_FROM_EMAIL", "FindX Platform <onboarding@resend.dev>")
                # On Resend sandbox/testing without custom verified domain, sender must be onboarding@resend.dev
                if "resend.dev" in sender or "localhost" in sender or "findx.local" in sender or "@gmail.com" in sender:
                    sender = "FindX Platform <onboarding@resend.dev>"

                payload = {
                    "from": sender,
                    "to": list(message.to),
                    "subject": message.subject,
                    "text": message.body,
                }
                if html_body:
                    payload["html"] = html_body

                req = urllib.request.Request(
                    "https://api.resend.com/emails",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "FindX-Platform/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status in (200, 201):
                        sent_count += 1
                        logger.info(f"Email successfully delivered via Resend API to {list(message.to)}")
            except urllib.error.HTTPError as e:
                err_detail = e.read().decode("utf-8")
                logger.error(f"Resend HTTP error ({e.code}): {err_detail}")
                if not self.fail_silently:
                    raise Exception(f"Resend API error: {err_detail}")
            except Exception as e:
                logger.error(f"Resend delivery error: {e}")
                if not self.fail_silently:
                    raise
        return sent_count
