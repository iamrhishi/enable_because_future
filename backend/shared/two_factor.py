"""
Email-OTP two-factor authentication.

Gated entirely by Config.TWO_FACTOR_AUTH_ENABLED (default False) - callers
should check that flag before touching anything here; login() does.
"""

from __future__ import annotations

import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import Config
from shared.database import db_manager
from shared.errors import AuthenticationError
from shared.logger import logger


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _is_fixed_otp_account(email: str) -> bool:
    fixed_emails = [
        e.strip().lower()
        for e in Config.TWO_FACTOR_FIXED_OTP_EMAILS.split(',')
        if e.strip()
    ]
    return (email or '').strip().lower() in fixed_emails


def generate_and_send_code(user_id: str, email: str) -> None:
    """
    Create a new 6-digit code for user_id and email it. Raises on send failure.

    Exception: accounts listed in Config.TWO_FACTOR_FIXED_OTP_EMAILS (App
    Store review demo account, internal QA) always get the same
    Config.TWO_FACTOR_FIXED_OTP_CODE instead of a random one, and it's never
    actually emailed - a reviewer can't check an inbox, and this can't be
    left dependent on SMTP being up during a live review.
    """
    is_fixed = _is_fixed_otp_account(email)
    code = Config.TWO_FACTOR_FIXED_OTP_CODE if is_fixed else f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now() + timedelta(minutes=Config.TWO_FACTOR_CODE_TTL_MINUTES)

    db_manager.execute_query(
        "INSERT INTO two_factor_codes (user_id, code_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, _hash_code(code), expires_at.strftime('%Y-%m-%d %H:%M:%S'))
    )

    if is_fixed:
        logger.info(f"two_factor: Fixed-OTP account ({email}) - code not emailed")
        return

    _send_code_email(email, code)


def _send_code_email(to_email: str, code: str) -> None:
    smtp_user = Config.TWO_FACTOR_SMTP_USER
    smtp_password = Config.TWO_FACTOR_SMTP_PASSWORD
    if not smtp_user or not smtp_password:
        logger.error("two_factor: TWO_FACTOR_SMTP_USER/PASSWORD not configured, cannot send code")
        raise AuthenticationError("Two-factor email could not be sent. Please try again later.")

    msg = MIMEMultipart()
    msg['From'] = Config.TWO_FACTOR_EMAIL_FROM
    msg['To'] = to_email
    msg['Subject'] = "Your BecauseFuture verification code"
    msg.attach(MIMEText(
        f"Your verification code is {code}.\n\n"
        f"It expires in {Config.TWO_FACTOR_CODE_TTL_MINUTES} minutes. "
        "If you didn't request this, you can ignore this email.",
        'plain'
    ))

    with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(Config.TWO_FACTOR_EMAIL_FROM, [to_email], msg.as_string())

    logger.info(f"two_factor: Code emailed to {to_email}")


def verify_code(user_id: str, submitted_code: str) -> bool:
    """
    Check submitted_code against the most recent unconsumed code for user_id.
    Returns True and consumes the code on success. Raises AuthenticationError
    on expiry/mismatch/too-many-attempts.
    """
    row = db_manager.execute_query(
        """SELECT id, code_hash, attempts, expires_at FROM two_factor_codes
           WHERE user_id = ? AND consumed_at IS NULL
           ORDER BY created_at DESC LIMIT 1""",
        (user_id,),
        fetch_one=True
    )

    if not row:
        raise AuthenticationError("No verification code found. Please request a new one.")

    if row['attempts'] >= Config.TWO_FACTOR_MAX_ATTEMPTS:
        raise AuthenticationError("Too many attempts. Please request a new code.")

    expires_at = datetime.strptime(row['expires_at'], '%Y-%m-%d %H:%M:%S')
    if datetime.now() > expires_at:
        raise AuthenticationError("Verification code expired. Please request a new one.")

    if _hash_code(submitted_code) != row['code_hash']:
        db_manager.execute_query(
            "UPDATE two_factor_codes SET attempts = attempts + 1 WHERE id = ?",
            (row['id'],)
        )
        raise AuthenticationError("Incorrect verification code.")

    db_manager.execute_query(
        "UPDATE two_factor_codes SET consumed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (row['id'],)
    )
    return True
