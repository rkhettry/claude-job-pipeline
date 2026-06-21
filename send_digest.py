#!/usr/bin/env python3
"""Email the daily digest via Gmail SMTP — no Chrome, fully headless.

Reads the digest markdown that the sourcing run writes
(automation/digest-YYYY-MM-DD.md), the recipient from config/user.yaml
(`digest_email`), and SMTP credentials from config/smtp.json. Sends a
multipart text+HTML email. Designed to run right after the sourcing Claude
exits, so the digest goes out whether or not Chrome was ever connected.

Usage:
  python3 automation/send_digest.py            # today's digest
  python3 automation/send_digest.py 2026-06-20 # a specific date

Exit codes: 0 sent · 2 no digest file · 3 no/invalid creds · 4 SMTP error.
config/smtp.json (gitignored) format — copy from config/smtp.example.json:
  {
    "sender_email": "you@gmail.com",
    "app_password": "abcd efgh ijkl mnop",   // Google App Password, not your login pw
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465
  }
"""

import json
import re
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

AUTOMATION_DIR = Path(__file__).resolve().parent
CONFIG_DIR = AUTOMATION_DIR / "config"
SMTP_CONF = CONFIG_DIR / "smtp.json"
USER_CONF = CONFIG_DIR / "user.yaml"


def _recipient():
    """digest_email from user.yaml without requiring a yaml dependency."""
    if not USER_CONF.exists():
        return None
    m = re.search(r'^\s*digest_email:\s*["\']?([^"\'\n#]+)', USER_CONF.read_text(), re.M)
    return m.group(1).strip() if m else None


def _subject_and_count(md_text, date_str):
    """Pull the digest title / new-count from the markdown's first heading."""
    m = re.search(r"#\s*Daily jobs digest[^\n]*", md_text)
    if m:
        return m.group(0).lstrip("# ").strip()
    return f"Daily jobs digest — {date_str}"


def _md_to_html(md_text):
    """Tiny markdown→HTML good enough for a digest email (headings, bold,
    links, list items, hr). Not a full parser — just readable formatting."""
    html_lines = []
    for line in md_text.splitlines():
        s = line.rstrip()
        if not s:
            html_lines.append("<br>")
            continue
        if s.startswith("> "):
            s = f'<blockquote style="color:#b45309;border-left:3px solid #f59e0b;padding-left:10px;margin:8px 0">{s[2:]}</blockquote>'
            html_lines.append(s)
            continue
        if s.strip() == "---":
            html_lines.append("<hr>")
            continue
        # inline: bold + links
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"(?<!\")(https?://[^\s<]+)", r'<a href="\1">\1</a>', s)
        h = re.match(r"(#{1,4})\s+(.*)", s)
        if h:
            level = len(h.group(1)) + 1
            html_lines.append(f"<h{level} style='margin:14px 0 6px'>{h.group(2)}</h{level}>")
        elif re.match(r"\s*[-*]\s+", s):
            html_lines.append(f"<li>{re.sub(r'^\s*[-*]\s+', '', s)}</li>")
        elif re.match(r"\s*\d+\.\s+", s):
            html_lines.append(f"<li>{re.sub(r'^\s*\d+\.\s+', '', s)}</li>")
        else:
            html_lines.append(f"<div>{s}</div>")
    body = "\n".join(html_lines)
    return (f'<div style="font-family:-apple-system,Segoe UI,sans-serif;'
            f'font-size:14px;line-height:1.5;color:#0f172a;max-width:760px">{body}</div>')


def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

    digest = AUTOMATION_DIR / f"digest-{date_str}.md"
    if not digest.exists():
        print(f"send_digest: no digest file for {date_str} ({digest.name}) — nothing to send")
        return 2

    recipient = _recipient()
    if not recipient:
        print("send_digest: no digest_email in config/user.yaml")
        return 3

    if not SMTP_CONF.exists():
        print(f"send_digest: missing {SMTP_CONF}. Copy config/smtp.example.json to "
              f"config/smtp.json and fill in a Gmail App Password.")
        return 3
    try:
        conf = json.loads(SMTP_CONF.read_text())
        sender = conf["sender_email"]
        password = conf["app_password"].replace(" ", "")  # Google shows it space-grouped
        host = conf.get("smtp_host", "smtp.gmail.com")
        port = int(conf.get("smtp_port", 465))
    except (json.JSONDecodeError, KeyError) as e:
        print(f"send_digest: bad config/smtp.json ({e})")
        return 3

    md_text = digest.read_text()
    subject = _subject_and_count(md_text, date_str)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(md_text, "plain", "utf-8"))
    msg.attach(MIMEText(_md_to_html(md_text), "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as server:
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        print("send_digest: SMTP auth failed — is app_password a valid Google App "
              "Password (not your normal login password)? Is 2FA on?")
        return 4
    except Exception as e:
        print(f"send_digest: SMTP send failed: {type(e).__name__}: {e}")
        return 4

    print(f"send_digest: sent '{subject}' to {recipient}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
