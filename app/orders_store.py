# app/orders_store.py
import os, json, threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_PATH = os.path.join(BASE_DIR, "orders.json")
_lock = threading.Lock()

def init_store():
    """Create a fresh orders.json with empty list every time server starts."""
    with _lock:
        data = {"orders": []}
        _write_unlocked(data)
    return ORDERS_PATH

def clear_store():
    """Wipe all orders (used on graceful shutdown)."""
    with _lock:
        _write_unlocked({"orders": []})
    print("🧹 Cleared orders.json on shutdown")

def _ensure_file_unlocked():
    if not os.path.exists(ORDERS_PATH):
        _write_unlocked({"orders": []})

def _read_unlocked():
    _ensure_file_unlocked()
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _write_unlocked(data):
    tmp = ORDERS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ORDERS_PATH)

def _read():
    with _lock:
        return _read_unlocked()

def _write(data):
    with _lock:
        _write_unlocked(data)

def add_order(order: dict):
    """Append a new order. Must include: order_number, phone, items, total, status, created_at."""
    with _lock:
        data = _read_unlocked()
        data["orders"].append(order)
        _write_unlocked(data)

def list_recent_orders(limit: int = 50):
    data = _read()
    items = list(reversed(data["orders"]))  # newest first
    return items[:limit]

def list_in_progress_orders(limit: int = 100):
    data = _read()
    items = [o for o in reversed(data["orders"]) if o.get("status") != "ready"]
    return [{"order_number": o["order_number"], "status": o.get("status", "received")} for o in items[:limit]]

def get_order_phone(order_number: str) -> str | None:
    data = _read()
    for o in data["orders"]:
        if o.get("order_number") == order_number:
            return o.get("phone")
    return None

def set_order_status(order_number: str, status: str) -> bool:
    with _lock:
        data = _read_unlocked()
        for o in data["orders"]:
            if o.get("order_number") == order_number:
                o["status"] = status
                _write_unlocked(data)
                return True
        return False

def set_order_sms_status(order_number: str, which: str, status: str, reason: str = "") -> bool:
    """Record the outcome of an SMS attempt on an already-stored order.

    `which` is "received" (order confirmation) or "ready" (pickup notice);
    `status` is "sent", "failed" or "skipped". The order is written first and
    the SMS attempted after, so this is how the real outcome gets back onto the
    record the dashboards read.
    """
    with _lock:
        data = _read_unlocked()
        for o in data["orders"]:
            if o.get("order_number") == order_number:
                o[f"sms_{which}"] = {"status": status, "reason": reason}
                if which == "received":
                    # what /staff keys its badge off
                    o["sms_status"] = status
                    o["sms_reason"] = reason
                    o["sms_capable"] = (status == "sent")
                _write_unlocked(data)
                return True
        return False

def get_order(order_number: str) -> dict | None:
    """Return full order dict by order_number."""
    data = _read()
    for o in data["orders"]:
        if o.get("order_number") == order_number:
            return o
    return None

def latest_order_for_phone(phone_e164: str) -> dict | None:
    """Return the most recent order for a phone (by created_at)."""
    data = _read()
    matches = [o for o in data["orders"] if o.get("phone") == phone_e164]
    if not matches:
        return None
    return sorted(matches, key=lambda o: o.get("created_at") or 0, reverse=True)[0]

def count_active_orders_for_phone(phone_e164: str) -> int:
    """Count orders for a phone that are NOT ready (active orders only)."""
    if not phone_e164:
        return 0
    data = _read()
    return sum(1 for o in data["orders"] if o.get("phone") == phone_e164 and o.get("status") != "ready")

def count_active_drinks_for_phone(phone_e164: str) -> int:
    """Count total number of drinks across all active orders (status != ready) for a phone."""
    if not phone_e164:
        return 0
    data = _read()
    total_drinks = 0
    for o in data["orders"]:
        if o.get("phone") == phone_e164 and o.get("status") != "ready":
            total_drinks += len(o.get("items", []))
    return total_drinks

def now_iso():
    return datetime.utcnow().isoformat()
