"""
Module 5 — Internal Alert & Escalation Service

Sends daily AP nudges and weekly CFO escalation reports.
Alerts are INTERNAL ONLY — never vendor-facing per spec.

Schedule:
  - Daily 9 AM IST: AP owner nudges ("N invoices cross deadline in 5 days, ₹X exposure")
  - Weekly Monday: CFO/Controller summary
  - Weekly Feb/Mar: Intensified escalation as March 31 approaches
  - NEVER send to vendors — buyer-side only

Channels: SMTP email (Gmail/Workspace free) + Slack free tier.
WhatsApp Business API is excluded (no longer meaningfully free since Meta 2025 pricing change).
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import json

import httpx

from app.core.config import settings


def _build_ap_nudge_html(invoices_at_risk: list[dict], total_exposure: Decimal) -> str:
    """Build HTML for the daily AP owner nudge email."""
    rows = ""
    for inv in invoices_at_risk:
        days = inv.get("days_remaining", 0)
        status_color = "#DC2626" if days <= 0 else "#D97706"
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #E5E7EB;">{inv.get('vendor_name','')}</td>
            <td style="padding:8px;border-bottom:1px solid #E5E7EB;">{inv.get('invoice_number','')}</td>
            <td style="padding:8px;border-bottom:1px solid #E5E7EB;color:{status_color};font-weight:bold;">
                {days} days {'overdue' if days <= 0 else 'remaining'}
            </td>
            <td style="padding:8px;border-bottom:1px solid #E5E7EB;">₹{inv.get('pending_amount', 0):,.2f}</td>
        </tr>
        """

    citation = settings.SECTION_CITATION_COMBINED
    return f"""
    <html><body style="font-family:Inter,sans-serif;background:#F9FAFB;padding:24px;">
    <div style="max-width:700px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <div style="background:#1E293B;padding:24px;color:white;">
            <h2 style="margin:0;font-size:20px;">⏱ VendorClock — Daily Compliance Alert</h2>
            <p style="margin:8px 0 0;color:#94A3B8;font-size:13px;">{citation}</p>
        </div>
        <div style="padding:24px;">
            <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-radius:8px;padding:16px;margin-bottom:24px;">
                <p style="margin:0;font-weight:600;color:#991B1B;">
                    ⚠ Total Tax Exposure at Risk: ₹{total_exposure:,.2f}
                </p>
            </div>
            <p style="color:#374151;">{len(invoices_at_risk)} invoice(s) require attention:</p>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <thead>
                    <tr style="background:#F3F4F6;">
                        <th style="padding:10px;text-align:left;">Vendor</th>
                        <th style="padding:10px;text-align:left;">Invoice</th>
                        <th style="padding:10px;text-align:left;">Deadline</th>
                        <th style="padding:10px;text-align:left;">Pending</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="margin-top:24px;font-size:12px;color:#6B7280;">
                This is an internal alert. Log in to VendorClock dashboard for the full cash-priority queue and one-click Form 3CD export.
                <br>⚠ Do not forward to vendors. Alerts are buyer-side only.
            </p>
        </div>
    </div>
    </body></html>
    """


def send_email(
    to: str,
    subject: str,
    html_body: str,
    attachment: Optional[bytes] = None,
    attachment_name: Optional[str] = None,
) -> bool:
    """Send an email via SMTP (Gmail/Workspace free tier)."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        print("[Alert] SMTP not configured — skipping email.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USERNAME}>"
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        if attachment and attachment_name:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={attachment_name}")
            msg.attach(part)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USERNAME, to, msg.as_string())
        return True
    except Exception as e:
        print(f"[Alert] Email send failed: {e}")
        return False


def send_slack_alert(text: str, blocks: Optional[list] = None) -> bool:
    """Send a Slack message via webhook (free tier)."""
    if not settings.SLACK_WEBHOOK_URL:
        print("[Alert] Slack webhook not configured — skipping.")
        return False

    try:
        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        response = httpx.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[Alert] Slack send failed: {e}")
        return False


def send_daily_ap_nudge(
    recipient: str,
    invoices_at_risk: list[dict],
    total_exposure: Decimal,
) -> bool:
    """Send daily AP owner nudge. INTERNAL ONLY — not vendor-facing."""
    if not invoices_at_risk:
        return True  # Nothing to send

    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    subject = f"[VendorClock] ⚠ {len(invoices_at_risk)} MSE invoices need attention — {today}"
    html = _build_ap_nudge_html(invoices_at_risk, total_exposure)
    sent = send_email(recipient, subject, html)

    # Also send Slack summary
    slack_text = (
        f"⏱ *VendorClock Daily Alert* — {today}\n"
        f"*{len(invoices_at_risk)} invoices* at risk of Section 43B(h)/37(2)(g) disallowance.\n"
        f"Total exposure: ₹{total_exposure:,.2f}\n"
        f"Log in to VendorClock dashboard to view the priority queue."
    )
    send_slack_alert(slack_text)
    return sent


def send_weekly_cfo_report(
    recipient: str,
    summary: dict,
    attachment: Optional[bytes] = None,
) -> bool:
    """Send weekly CFO/Controller escalation report. INTERNAL ONLY."""
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    is_march_approaching = datetime.now(timezone.utc).month in (2, 3)
    urgency = "🚨 URGENT — March 31 approaching! " if is_march_approaching else ""

    subject = f"[VendorClock] {urgency}Weekly CFO Compliance Report — {today}"
    html = f"""
    <html><body style="font-family:Inter,sans-serif;background:#F9FAFB;padding:24px;">
    <div style="max-width:700px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <div style="background:#1E293B;padding:24px;color:white;">
            <h2 style="margin:0;">📊 VendorClock — Weekly CFO Report</h2>
            <p style="margin:8px 0 0;color:#94A3B8;font-size:13px;">{settings.SECTION_CITATION_COMBINED}</p>
        </div>
        <div style="padding:24px;">
            {'<div style="background:#FEF2F2;border:1px solid #FCA5A5;border-radius:8px;padding:16px;margin-bottom:24px;"><strong>🚨 March 31 is approaching — all overdue MSE dues will be disallowed for FY 2025-26.</strong></div>' if is_march_approaching else ''}
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:12px;background:#F9FAFB;border-radius:4px;font-weight:600;">Total Eligible MSE Invoices</td><td style="padding:12px;">{summary.get('total_invoices', 0)}</td></tr>
                <tr><td style="padding:12px;font-weight:600;">RED (Overdue)</td><td style="padding:12px;color:#DC2626;font-weight:600;">{summary.get('red_count', 0)}</td></tr>
                <tr><td style="padding:12px;background:#F9FAFB;font-weight:600;">AMBER (Due in 7 days)</td><td style="padding:12px;color:#D97706;font-weight:600;">{summary.get('amber_count', 0)}</td></tr>
                <tr><td style="padding:12px;font-weight:600;">Total ₹ at Risk of Disallowance</td><td style="padding:12px;font-weight:600;">₹{summary.get('total_exposure', 0):,.2f}</td></tr>
                <tr><td style="padding:12px;background:#F9FAFB;font-weight:600;">Accrued Non-Deductible Interest</td><td style="padding:12px;color:#DC2626;">₹{summary.get('total_interest', 0):,.2f}</td></tr>
            </table>
            <p style="margin-top:24px;font-size:12px;color:#6B7280;">Internal CFO report. See attached Form 3CD draft for your CA.</p>
        </div>
    </div></body></html>
    """
    return send_email(recipient, subject, html, attachment=attachment, attachment_name="form_3cd_draft.xlsx")
