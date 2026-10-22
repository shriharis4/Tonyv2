"""
Real email sending via SMTP, configured through environment variables.

Closes the gap where `send_email` was referenced in AGENT_INSTRUCTION_FOR_TOOLS
but no such tool existed anywhere in Tools/ — previously this caused Gemini
to attempt and silently fail a tool call with no matching function.

Required .env vars (see README / .env.example):
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
If any are missing, the tool returns a clear "email isn't configured"
message rather than raising or silently no-op-ing.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from livekit.agents import function_tool

from Tools.tool_result import ok, fail


def _smtp_config() -> Optional[dict]:
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", username)

    if not all([host, port, username, password]):
        return None
    try:
        port_int = int(port)
    except ValueError:
        return None
    return {
        "host": host,
        "port": port_int,
        "username": username,
        "password": password,
        "from_email": from_email,
    }


def _send_sync(config: dict, to: str, subject: str, message: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = config["from_email"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))

    with smtplib.SMTP(config["host"], config["port"], timeout=10) as server:
        server.starttls()
        server.login(config["username"], config["password"])
        server.sendmail(config["from_email"], [to], msg.as_string())


@function_tool()
async def send_email(to: str, subject: str, message: str) -> str:
    """
    Send an email via the configured SMTP provider.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        message: Plain-text email body.

    Returns:
        Structured success/failure string. If SMTP is not configured in
        .env (SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD), returns a
        clear "email isn't configured" message rather than a silent no-op.
    """
    if not to or "@" not in to:
        return fail(f"'{to}' doesn't look like a valid email address.")
    if not subject or not subject.strip():
        return fail("No subject provided.")
    if not message or not message.strip():
        return fail("No message body provided.")

    config = _smtp_config()
    if not config:
        return fail(
            "Email isn't configured yet.",
            detail="Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD "
            "(and optionally SMTP_FROM_EMAIL) in .env to enable sending.",
        )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_sync, config, to, subject, message)
        return ok(f"Email sent to {to}", detail=f"subject={subject}")
    except smtplib.SMTPAuthenticationError:
        return fail("SMTP authentication failed.", detail="Check SMTP_USERNAME/SMTP_PASSWORD in .env.")
    except (smtplib.SMTPException, OSError) as e:
        return fail("Failed to send email", detail=str(e))
