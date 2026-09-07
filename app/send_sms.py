# app/send_sms.py
import logging
import os
import re
from dotenv import load_dotenv
from twilio.rest import Client
from .business_logic import CONFIG

load_dotenv()

SID  = os.environ.get("MSG_TWILIO_ACCOUNT_SID")
TOK  = os.environ.get("MSG_TWILIO_AUTH_TOKEN")
FROM = os.environ.get("MSG_TWILIO_FROM_E164")

log = logging.getLogger("send_sms")

_client = Client(SID, TOK) if SID and TOK else None
E164_RE = re.compile(r"^\+\d{10,15}$")

# Twilio error codes worth translating into something a barista can act on.
# https://www.twilio.com/docs/api/errors
_TWILIO_REASONS = {
    20003: "messaging credentials rejected (no messaging-enabled number?)",
    21211: "Twilio says this number is invalid",
    21408: "SMS to this country is not enabled on the Twilio account",
    21606: "the Twilio 'from' number can't send SMS",
    21612: "Twilio can't route SMS to this number",
    21614: "this number can't receive SMS",
}


def _sms_result(ok: bool, reason: str = "", sid: str | None = None) -> dict:
    """Outcome of one send attempt. Never raises, so callers can record it."""
    return {"ok": ok, "reason": reason, "sid": sid}


def _send(kind: str, order_no: str, to_phone_no: str, body: str) -> dict:
    """Send one SMS and report what actually happened."""
    if not _client:
        log.error("❌ Twilio client not configured")
        return _sms_result(False, "messaging not configured")
    if not _ok_e164(to_phone_no):
        log.error(f"❌ Invalid E.164 phone for SMS: {to_phone_no}")
        return _sms_result(False, "not a valid phone number")

    try:
        msg = _client.messages.create(from_=FROM, to=to_phone_no, body=body)
    except Exception as e:
        # TwilioRestException carries .status/.code/.msg; anything else (network,
        # DNS) just gets its class name.
        code = getattr(e, "code", None)
        status = getattr(e, "status", None)
        if code in _TWILIO_REASONS:
            reason = _TWILIO_REASONS[code]
        elif status == 401:
            reason = "messaging credentials rejected (no messaging-enabled number?)"
        elif code:
            reason = f"Twilio error {code}"
        else:
            reason = f"{type(e).__name__}"
        log.warning(f"❌ SMS ({kind}) to {to_phone_no} failed for order {order_no}: {reason} [{e}]")
        return _sms_result(False, reason)

    log.info(f"📱 SMS ({kind}) to {to_phone_no}: order {order_no}")
    return _sms_result(True, sid=getattr(msg, "sid", None))

_SMS = CONFIG.get("sms", {})
_BRAND = CONFIG["brand"]

def _fmt(template: str, order_no: str) -> str:
    return template.format(
        brand_name=_BRAND["name"],
        brand_emoji=_BRAND["emoji"],
        order_number=order_no,
    )

def _ok_e164(p: str | None) -> bool:
    return bool(p and E164_RE.fullmatch(p))

def send_received_sms(order_no: str, to_phone_no: str) -> dict:
    """Confirmation SMS (sent right after order is placed).

    Returns {"ok", "reason", "sid"} — the first real signal of whether SMS works
    for this order, which is what the dashboards key their message off.
    """
    body = _fmt(_SMS.get("order_received",
        "Thanks for your order with {brand_name}! {brand_emoji} Your order number is {order_number}. We’ll text you again when it’s ready for pickup.\nReply STOP to opt out."
    ), order_no)
    return _send("received", order_no, to_phone_no, body)

def send_ready_sms(order_no: str, to_phone_no: str) -> dict:
    """Notify order is ready (triggered by /staff Done). Same result shape."""
    body = _fmt(_SMS.get("order_ready",
        "Hi! Your order #{order_number} is now ready for pickup at {brand_name}. {brand_emoji} See you soon!\nReply STOP to opt out."
    ), order_no)
    return _send("ready", order_no, to_phone_no, body)
