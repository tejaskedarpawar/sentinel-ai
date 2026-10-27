"""
Outbound alert notifications for Sentinel AI.
Supported channels:
  1. Slack incoming webhook
  2. Telegram bot (token + chat_id)
  3. SMTP email (host, port, user, password, from, to, tls)

Privacy-first: Notifications strictly convey metadata (employee ID, date,
risk tier, score, rule flags, and case URL). No file names, contents,
or raw behavioural payload details are ever transmitted.

All channels are optional and fail-safe: failures are logged and will
never disrupt the detection pipeline or real-time event streaming.
Alerts are deduplicated per (employee_id, date) with a 24-hour Redis TTL.
"""
import logging
from email.message import EmailMessage
import smtplib
import httpx
import redis

from app.config import settings

logger = logging.getLogger(__name__)

# Redis client for deduplication
_redis = redis.from_url(settings.redis_url, decode_responses=True)

TIER_RANKS = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Critical": 4,
}


def get_notification_channels_status() -> dict:
    """Return configured status of all notification channels without exposing secrets."""
    return {
        "min_tier": settings.notifier_min_tier,
        "dashboard_base_url": settings.dashboard_base_url,
        "channels": {
            "slack": {
                "name": "Slack Webhook",
                "configured": bool(settings.slack_webhook_url),
            },
            "telegram": {
                "name": "Telegram Bot",
                "configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
            },
            "email": {
                "name": "SMTP Email",
                "configured": bool(settings.smtp_host and settings.smtp_from and settings.smtp_to),
            },
        },
    }


def _format_rule_flags(flags) -> str:
    if isinstance(flags, list) and flags:
        return ", ".join(str(f) for f in flags)
    if isinstance(flags, str) and flags:
        return flags
    return "None"


def _send_slack(employee_id: str, date: str, tier: str, score: float, flags_str: str, case_url: str) -> tuple[bool, str]:
    if not settings.slack_webhook_url:
        return False, "not_configured"

    summary_text = f"🚨 Sentinel AI [{tier}] Alert: Employee {employee_id} on {date} (Risk: {score:.1f})"
    payload = {
        "text": summary_text,
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚨 Sentinel AI [{tier}] Alert", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Employee ID:*\n`{employee_id}`"},
                    {"type": "mrkdwn", "text": f"*Date:*\n{date}"},
                    {"type": "mrkdwn", "text": f"*Risk Tier:*\n*{tier}*"},
                    {"type": "mrkdwn", "text": f"*Risk Score:*\n`{score:.1f}`"},
                    {"type": "mrkdwn", "text": f"*Rule Flags:*\n{flags_str}"},
                    {"type": "mrkdwn", "text": f"*Case Link:*\n<{case_url}|Open Case in SOC Dashboard>"},
                ],
            },
        ],
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(settings.slack_webhook_url, json=payload)
            if resp.status_code >= 400:
                msg = f"Slack webhook returned HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error(msg)
                return False, msg
            return True, "sent"
    except Exception as exc:
        msg = f"Slack webhook error: {exc}"
        logger.exception(msg)
        return False, msg


def _send_telegram(employee_id: str, date: str, tier: str, score: float, flags_str: str, case_url: str) -> tuple[bool, str]:
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return False, "not_configured"

    text = (
        f"🚨 *Sentinel AI [{tier}] Alert*\n\n"
        f"• *Employee ID:* `{employee_id}`\n"
        f"• *Date:* `{date}`\n"
        f"• *Risk Tier:* *{tier}*\n"
        f"• *Risk Score:* `{score:.1f}`\n"
        f"• *Rule Flags:* `{flags_str}`\n\n"
        f"🔗 [Open Case in SOC Dashboard]({case_url})"
    )

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code >= 400:
                msg = f"Telegram API returned HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error(msg)
                return False, msg
            return True, "sent"
    except Exception as exc:
        msg = f"Telegram send error: {exc}"
        logger.exception(msg)
        return False, msg


def _send_email(employee_id: str, date: str, tier: str, score: float, flags_str: str, case_url: str) -> tuple[bool, str]:
    if not (settings.smtp_host and settings.smtp_from and settings.smtp_to):
        return False, "not_configured"

    msg = EmailMessage()
    msg["Subject"] = f"[Sentinel AI] {tier} Alert: {employee_id} ({date})"
    msg["From"] = settings.smtp_from
    msg["To"] = settings.smtp_to

    body = (
        f"Sentinel AI Security Alert\n"
        f"=========================\n\n"
        f"Anomalous activity exceeded risk thresholds.\n\n"
        f"Employee ID:  {employee_id}\n"
        f"Date:         {date}\n"
        f"Risk Tier:    {tier}\n"
        f"Risk Score:   {score:.1f}\n"
        f"Rule Flags:   {flags_str}\n\n"
        f"SOC Case Dossier: {case_url}\n\n"
        f"--\n"
        f"Sentinel AI Detection Pipeline (Automated Notification)\n"
        f"Privacy-preserving metadata only. No payload or file contents are recorded.\n"
    )
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5.0) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True, "sent"
    except Exception as exc:
        msg_err = f"SMTP send error: {exc}"
        logger.exception(msg_err)
        return False, msg_err


def notify_alert(alert: dict, force: bool = False) -> dict:
    """
    Dispatch notifications across all configured channels for an alert.
    Deduplicates per (employee_id, date) with a 24-hour TTL in Redis unless force=True.
    Failsafe: Never raises an exception to the caller.
    """
    employee_id = str(alert.get("employee_id", "UNKNOWN"))
    date = str(alert.get("date", "UNKNOWN"))
    tier = str(alert.get("risk_tier", "High"))
    score = float(alert.get("risk_score", 0.0))
    flags_str = _format_rule_flags(alert.get("rule_flags"))
    case_url = f"{settings.dashboard_base_url.rstrip('/')}/?case={employee_id}&date={date}"

    # Verify minimum tier
    required_rank = TIER_RANKS.get(settings.notifier_min_tier, 4)
    alert_rank = TIER_RANKS.get(tier, 0)
    if alert_rank < required_rank and not force:
        return {
            "status": "skipped",
            "reason": f"tier_{tier}_below_minimum_{settings.notifier_min_tier}",
        }

    # Deduplicate via Redis key
    dedup_key = f"sentinel:notified:{employee_id}:{date}"
    try:
        if not force:
            # Atomic set if not exists, 24-hour TTL (86400s)
            was_set = _redis.set(dedup_key, "1", nx=True, ex=86400)
            if not was_set:
                logger.info(f"Skipping notification for {employee_id} {date}: already notified")
                return {"status": "skipped", "reason": "deduplicated"}
        else:
            _redis.set(dedup_key, "1", ex=86400)
    except Exception as exc:
        logger.warning(f"Redis dedup check error ({exc}), proceeding with notification")

    results = {}

    # Slack
    slack_ok, slack_msg = _send_slack(employee_id, date, tier, score, flags_str, case_url)
    results["slack"] = slack_msg if not slack_ok else "sent"

    # Telegram
    tg_ok, tg_msg = _send_telegram(employee_id, date, tier, score, flags_str, case_url)
    results["telegram"] = tg_msg if not tg_ok else "sent"

    # SMTP Email
    mail_ok, mail_msg = _send_email(employee_id, date, tier, score, flags_str, case_url)
    results["email"] = mail_msg if not mail_ok else "sent"

    return {
        "status": "completed",
        "employee_id": employee_id,
        "date": date,
        "tier": tier,
        "results": results,
    }


def send_test_notification() -> dict:
    """Send a test notification with simulated metadata to all configured channels."""
    test_alert = {
        "employee_id": "TEST_EMP_999",
        "date": "2024-10-24",
        "risk_tier": "Critical",
        "risk_score": 96.5,
        "rule_flags": ["TEST_DISPATCH_EVENT", "HIGH_VOLUME_COPY"],
    }
    return notify_alert(test_alert, force=True)
