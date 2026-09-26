"""Outgoing e-mail, for password recovery only.

Plain SMTP with STARTTLS, configured by the environment:

    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM (SMTP_USER)

Without SMTP_HOST nothing is sent: the message is printed to the backend's log
instead, which is enough to follow a reset link in development.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send(to: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"[mailer] SMTP_HOST unset, not sending to {to}: {subject}\n{body}", flush=True)
        return
    user = os.environ.get("SMTP_USER", "")
    msg = EmailMessage()
    msg["From"] = os.environ.get("MAIL_FROM") or user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=20) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
