"""Gmail SMTP tool for Doug's operational summaries.

Subject is always constant to maintain email threading.
Thread ID stored in state.json, not a separate file.
"""

import email.message
import logging
import os
import smtplib
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def send_gmail(subject: str, body: str) -> dict:
    """Send an operational email via Gmail SMTP.

    Args:
        subject: Email subject line (should be constant for threading).
        body: Email body text.

    Returns:
        Dict with status and message_id for threading.
    """
    address = os.environ.get("GMAIL_ADDRESS", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not address or not password:
        logger.warning("Gmail credentials not set, skipping email")
        return {"status": "skipped", "reason": "credentials not set"}

    msg = email.message.EmailMessage()
    msg["Subject"] = subject
    msg["From"] = address
    msg["To"] = address  # Doug emails Stefano (same address)
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(address, password)
            server.send_message(msg)

        message_id = msg.get("Message-ID", "")
        logger.info(f"Email sent: {subject}")
        return {"status": "sent", "message_id": message_id}

    except Exception as e:
        logger.error(f"Gmail send failed: {e}")
        return {"status": "error", "error": str(e)}
