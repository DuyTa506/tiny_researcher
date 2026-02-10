"""
Email service for verification and password reset.

Sends emails via SMTP. Falls back to logging in development when SMTP is not configured.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Send transactional emails via SMTP."""

    @property
    def is_configured(self) -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_USER)

    def _send(self, to: str, subject: str, html_body: str):
        """Send an email. Logs in development if SMTP not configured."""
        if not self.is_configured:
            logger.info(f"[EMAIL-DEV] To: {to} | Subject: {subject}")
            logger.info(f"[EMAIL-DEV] Body: {html_body[:300]}...")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Email sent to {to}: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")

    def send_verification_email(self, to: str, token: str):
        link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
        html = f"""
        <h2>Verify your email</h2>
        <p>Click the link below to verify your email address:</p>
        <p><a href="{link}">{link}</a></p>
        <p>This link expires in 24 hours.</p>
        """
        self._send(to, "Verify your email - Tiny Researcher", html)

    def send_password_reset_email(self, to: str, token: str):
        link = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        html = f"""
        <h2>Reset your password</h2>
        <p>Click the link below to reset your password:</p>
        <p><a href="{link}">{link}</a></p>
        <p>This link expires in 1 hour. If you did not request this, ignore this email.</p>
        """
        self._send(to, "Password reset - Tiny Researcher", html)
