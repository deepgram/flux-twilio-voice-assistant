# app/agent_functions.py
from typing import Any, Dict, Optional
import asyncio

from . import business_logic as bl
from .session import sessions
from .events import publish  # NEW

# ---------- Tool implementations (per-call) ----------
async def _add_to_cart(flavor: str, addons=None, sweetness: str | None = None,
                       ice: str | None = None, *, call_sid: str | None = None):
    return await bl.add_to_cart(flavor, addons, sweetness, ice, call_sid=call_sid)

async def _remove_from_cart(index: int, *, call_sid: str | None = None):
    return await bl.remove_from_cart(index, call_sid=call_sid)

async def _modify_cart_item(index: int, flavor: str | None = None, addons=None,
                            sweetness: str | None = None, ice: str | None = None,
                            *, call_sid: str | None = None):
    return await bl.modify_cart_item(index, flavor, addons, sweetness, ice, call_sid=call_sid)

async def _set_sweetness_ice(index: int | None = None, sweetness: str | None = None,
                             ice: str | None = None, *, call_sid: str | None = None):
    return await bl.set_sweetness_ice(index, sweetness, ice, call_sid=call_sid)

async def _get_cart(*, call_sid: str | None = None):
    return await bl.get_cart(call_sid=call_sid)

async def _checkout_order(phone: str | None = None, *, call_sid: str | None = None):
    # Generate order number, but do not finalize.
    res = await bl.checkout_order(phone, call_sid=call_sid)
    if isinstance(res, dict) and res.get("ok"):
        s = await sessions.get_or_create(call_sid or "unknown")
        if res.get("phone"):
            s.phone = res["phone"]
            # NOTE: do NOT auto-confirm here; explicit confirmation is required.
        if res.get("order_number"):
            s.order_number = res["order_number"]
            # 🔔 Tell dashboards an order number was assigned (pre-finalize)
            await publish("orders", {
                "type": "order_locked",
                "order_number": s.order_number,
                "call_sid": call_sid
            })
    return res

async def _order_status(phone: str | None = None, order_number: str | None = None,
                        *, call_sid: str | None = None):
    return await bl.order_status(phone, order_number, call_sid=call_sid)

def _menu_summary():
    return bl.menu_summary()

def _extract_phone_and_order(text: str):
    return bl.extract_phone_and_order(text)

def _spell_last_four(phone: str | None) -> str:
    """Return last 4 digits spaced out so TTS reads them individually."""
    if not phone:
        return ""
    digits = [c for c in phone if c.isdigit()]
    return " ".join(digits[-4:]) if len(digits) >= 4 else " ".join(digits)

async def _save_phone_number(phone: str | None = None, *, call_sid: str | None = None):
    from .business_logic import normalize_phone
    s = await sessions.get_or_create(call_sid or "unknown")
    if phone:
        p = normalize_phone(phone)
        s.phone = p
    else:
        p = s.phone  # use pre-filled caller ID
    s.phone_confirmed = False
    return {"ok": bool(p), "phone": p, "last_four_spoken": _spell_last_four(p)}

# NEW: explicit confirmation tool (minimal addition)
async def _confirm_phone_number(confirmed: bool, *, call_sid: str | None = None):
    s = await sessions.get_or_create(call_sid or "unknown")
    s.phone_confirmed = bool(confirmed) and bool(s.phone)
    return {"ok": s.phone_confirmed, "phone": s.phone, "last_four_spoken": _spell_last_four(s.phone)}

# Back-compat no-ops for staged flow (so the prompt doesn’t break)
async def _confirm_pending_to_cart(*, call_sid: str | None = None):
    # Our add_to_cart writes directly. Nothing to confirm.
    return {"ok": True, "staged": False}

async def _clear_pending_item(*, call_sid: str | None = None):
    # No staged item; just a no-op.
    return {"ok": True, "cleared": True}

async def _order_is_placed(*, call_sid: str | None = None):
    s = await sessions.get_or_create(call_sid or "unknown")
    placed = bool(s.order_number)
    return {"placed": placed, "order_number": s.order_number}

# ---------- Tool definitions (Deepgram Agent expects this schema) ----------
FUNCTION_DEFS: list[Dict[str, Any]] = [
    {
        "name": "menu_summary",
        "description": "Give a short human-style menu overview (drinks and add-ons).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # Cart ops
    {
        "name": "add_to_cart",
        "description": "Add a drink to the cart (standard size).",
        "parameters": {
            "type": "object",
            "properties": {
                "flavor": {"type": "string"},
                "addons": {"type": "array", "items": {"type": "string"}, "description": "Any add-ons: milk choices, syrups, etc."},
                "sweetness": {"type": "string", "description": "0% | 25% | 50% | 75% | 100%"},
                "ice": {"type": "string", "description": "no ice | less ice | regular ice | extra ice"},
            },
            "required": ["flavor"],
        },
    },
    {
        "name": "remove_from_cart",
        "description": "Remove a drink by index (0-based).",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer", "minimum": 0}},
            "required": ["index"],
        },
    },
    {
        "name": "modify_cart_item",
        "description": "Modify an existing drink in the cart by index.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 0},
                "flavor": {"type": "string"},
                "addons": {"type": "array", "items": {"type": "string"}, "description": "Any add-ons: milk choices, syrups, etc."},
                "sweetness": {"type": "string"},
                "ice": {"type": "string"},
            },
            "required": ["index"],
        },
    },
    {
        "name": "set_sweetness_ice",
        "description": "Update sweetness and/or ice for last item or by index.",
        "parameters": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "minimum": 0},
                "sweetness": {"type": "string"},
                "ice": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "get_cart",
        "description": "Get current cart contents to read back to customer.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # Session helpers (compat)
    {
        "name": "order_is_placed",
        "description": "Return whether an order number has been generated in this call session.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },

    # Checkout / status
    {
        "name": "checkout_order",
        "description": "Generate order number but don't finalize yet. Can be called once per order flow.",
        "parameters": {
            "type": "object",
            "properties": {"phone": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "order_status",
        "description": "Look up order status by phone or order number.",
        "parameters": {
            "type": "object",
            "properties": {"phone": {"type": "string"}, "order_number": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "extract_phone_and_order",
        "description": "Extract phone and 4-digit order number from free text.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },

    # Phone capture + confirmation (NEW)
    {
        "name": "save_phone_number",
        "description": "Save or retrieve the customer's phone number for pickup. If no phone is provided, returns the caller ID number already on file.",
        "parameters": {
            "type": "object",
            "properties": {"phone": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "confirm_phone_number",
        "description": "Confirm (true) or reject (false) the previously provided phone number.",
        "parameters": {
            "type": "object",
            "properties": {"confirmed": {"type": "boolean"}},
            "required": ["confirmed"],
        },
    },

    # Back-compat stubs (no staging in this build)
    {"name": "confirm_pending_to_cart", "description": "No-op in this build.", "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "clear_pending_item", "description": "No-op in this build.", "parameters": {"type": "object", "properties": {}, "required": []}},
]

# --- Map tool names to functions ---
FUNCTION_MAP: dict[str, Any] = {
    "menu_summary": _menu_summary,
    "add_to_cart": _add_to_cart,
    "remove_from_cart": _remove_from_cart,
    "modify_cart_item": _modify_cart_item,
    "set_sweetness_ice": _set_sweetness_ice,
    "get_cart": _get_cart,
    "order_is_placed": _order_is_placed,
    "checkout_order": _checkout_order,
    "order_status": _order_status,
    "extract_phone_and_order": _extract_phone_and_order,
    "save_phone_number": _save_phone_number,
    "confirm_phone_number": _confirm_phone_number,  # NEW
    "confirm_pending_to_cart": _confirm_pending_to_cart,
    "clear_pending_item": _clear_pending_item,
}
