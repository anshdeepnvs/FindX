"""
claims/emails.py — Sends email notifications to finders when AI verifies a genuine owner.
"""

import logging
import os
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)


def send_ai_verified_claim_email(finder, claimant, found_item, match, claim, convo_id=None):
    """
    Sends a transactional notification email to the finder alerting them that a genuine
    owner has been verified by FindX AI with >= 70% confidence score.
    Engineered with anti-spam compliance: clean subject, no spam trigger words/emojis,
    proper transactional headers, and domain link.
    """
    if not finder.email:
        return False

    base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    if convo_id:
        chat_link = f"{base_url}/chat/{convo_id}/"
    else:
        chat_link = f"{base_url}/matching/{match.id}/"

    score_display = f"{claim.ai_score:.0f}%" if claim.ai_score is not None else "70%+"
    claimant_name = claimant.get_full_name_or_username()
    finder_name = finder.get_full_name_or_username()

    # Clean, professional subject without spam trigger emojis or spammy words
    subject = f"[FindX] Ownership verification update for your found item: {found_item.title}"

    text_content = (
        f"Hello {finder_name},\n\n"
        f"An ownership claim submitted for the item you found ('{found_item.title}') has been verified by FindX.\n\n"
        f"Claimant: {claimant_name}\n"
        f"AI Verification Match Score: {score_display}\n\n"
        f"Please open the secure chat to review the claimant's answers and uploaded proof:\n"
        f"{chat_link}\n\n"
        f"Once you review and accept the claimant as a probable owner in chat, direct chat will unlock to coordinate the return and a safe Handover OTP will be issued for in-person verification.\n\n"
        f"Best regards,\n"
        f"FindX Community Safety Team\n"
        f"support.findx@gmail.com\n"
        f"---\n"
        f"This is an automated transactional message regarding your found item report on FindX."
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>FindX Ownership Verification</title>
</head>
<body style="font-family: Arial, Helvetica, sans-serif; background-color: #f8fafc; margin: 0; padding: 28px 16px; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px;">
    <tr>
      <td>
        <!-- Header -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 24px;">
          <tr>
            <td>
              <h2 style="margin: 0; font-size: 22px; color: #0f172a; font-weight: bold; letter-spacing: -0.5px;">
                Find<span style="color: #0284c7;">X</span>
              </h2>
            </td>
            <td align="right">
              <span style="display: inline-block; background-color: #f0fdf4; color: #166534; font-size: 11px; padding: 4px 10px; border-radius: 999px; font-weight: bold; border: 1px solid #bbf7d0;">
                AI VERIFIED
              </span>
            </td>
          </tr>
        </table>

        <!-- Greeting -->
        <p style="font-size: 15px; line-height: 1.5; color: #334155; margin: 0 0 16px;">
          Hello <strong>{finder_name}</strong>,
        </p>

        <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 0 0 20px;">
          Thank you for reporting <strong>"{found_item.title}"</strong> on FindX. An ownership claim submitted by <strong>{claimant_name}</strong> has passed our AI ownership verification interview.
        </p>

        <!-- Verification Score Card -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; margin: 20px 0; text-align: center;">
          <tr>
            <td style="padding: 18px;">
              <div style="font-size: 11px; font-weight: bold; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">
                AI Verification Match Score
              </div>
              <div style="font-size: 32px; font-weight: bold; color: #0f766e;">
                {score_display} Match
              </div>
              <div style="font-size: 12px; color: #0f766e; margin-top: 4px;">
                Claimant successfully answered confidential security questions.
              </div>
            </td>
          </tr>
        </table>

        <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 0 0 24px;">
          Please review the full verification interview and claimant's answers in the chat. You can then accept and confirm the owner to unlock the safe Handover OTP.
        </p>

        <!-- CTA Button -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0; text-align: center;">
          <tr>
            <td align="center">
              <a href="{chat_link}" style="display: inline-block; background-color: #0f172a; color: #ffffff; text-decoration: none; padding: 13px 28px; border-radius: 8px; font-weight: bold; font-size: 14px;">
                Review Chat &amp; Coordinate Return
              </a>
            </td>
          </tr>
        </table>

        <!-- Security Note -->
        <div style="background-color: #f1f5f9; border-radius: 8px; padding: 14px 16px; border: 1px solid #e2e8f0; font-size: 12px; color: #475569; line-height: 1.5; margin-top: 24px;">
          <strong style="color: #1e293b;">Next Step:</strong> After you accept the claimant as a probable owner in chat, direct messaging unlocks to coordinate the return and a 6-digit Handover OTP will be issued for in-person verification.
        </div>

        <!-- Transactional Footer -->
        <div style="border-top: 1px solid #e2e8f0; margin-top: 28px; padding-top: 16px; font-size: 11px; color: #94a3b8; line-height: 1.5;">
          You received this notification because you submitted a found item report on FindX.<br>
          FindX Community Safety &bull; support.findx@gmail.com
        </div>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # From address format with proper sender display name
    sender_name = "FindX Platform"
    sender_email = getattr(settings, "EMAIL_HOST_USER", "support.findx@gmail.com") or "support.findx@gmail.com"
    from_header = f'"{sender_name}" <{sender_email}>'

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_header,
            to=[finder.email],
            reply_to=[sender_email],
            headers={
                "Auto-Submitted": "auto-generated",
                "X-Auto-Response-Suppress": "All",
                "X-Entity-Ref-ID": f"findx-claim-{claim.id}",
                "Precedence": "bulk",
            },
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"AI verified claim email successfully sent to {finder.email}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send AI verified claim email to {finder.email}: {e}")
        return False

