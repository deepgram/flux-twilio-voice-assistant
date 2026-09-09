# app/http_routes.py
import os
import json as _json
import asyncio
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, JSONResponse, HTMLResponse, StreamingResponse

from .orders_store import (
    list_recent_orders,
    list_in_progress_orders,
    get_order_phone,
    set_order_status,
    set_order_sms_status,
    add_order,
    get_order,  # full order lookup
)
from .events import subscribe, unsubscribe, publish
from .send_sms import send_ready_sms
from .business_logic import CONFIG

# Optional call log appends (if file/module exists)
try:
    from .call_logger import append_for_phone  # type: ignore
except Exception:
    append_for_phone = None  # safe fallback

log = logging.getLogger("http")
http_router = APIRouter()

# -------------------- Helpers --------------------

def _host_and_scheme() -> tuple[str, str]:
    host = os.getenv("VOICE_HOST", "localhost:8000")
    # Allow explicit override by WS_SCHEME (wss / ws)
    ws_scheme = os.getenv("WS_SCHEME")
    if ws_scheme:
        scheme = ws_scheme.strip().lower()
    else:
        scheme = "wss" if not host.startswith("localhost") else "ws"
    return host, scheme

def _autorefresh_meta(refresh_seconds: Optional[int]) -> str:
    if not refresh_seconds or refresh_seconds <= 0:
        return ""
    return f'<meta http-equiv="refresh" content="{int(refresh_seconds)}" />'

_THEME_DEFAULTS = {
    "font_family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "bg_gradient": "linear-gradient(135deg, #050506 0%, #1a1a1f 100%)",
    "card_bg": "#1a1a1f",
    "card_text": "#fbfbff",
    "card_muted": "#949498",
    "accent": "#13ef95",
    "accent_hover_shadow": "rgba(19,239,149,0.2)",
    "border": "#2c2c33",
    "orders_tv_bg": "#0b0b0c",
    "orders_tv_card_bg": "#1a1a1f",
    "orders_tv_border": "#2c2c33",
    "orders_tv_text": "#fbfbff",
}

def _theme() -> dict:
    return {k: CONFIG.get("theme", {}).get(k, v) for k, v in _THEME_DEFAULTS.items()}

# -------------------- Landing page --------------------

def _index_html():
    _b = CONFIG["brand"]
    t = _theme()
    font = t["font_family"]
    bg = t["bg_gradient"]
    card_bg = t["card_bg"]
    card_text = t["card_text"]
    card_muted = t["card_muted"]
    accent = t["accent"]
    accent_shadow = t["accent_hover_shadow"]
    border = t["border"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{_b["emoji"]} {_b["name"]} - {_b["tagline"]}</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: {font};
           min-height:100vh; display:grid; place-items:center;
           background: {bg}; }}
    .card {{ background: {card_bg}; border: 1px solid {border}; border-radius: 20px; padding: 32px; max-width: 900px; width: 94%;
            box-shadow: 0 18px 60px rgba(0,0,0,0.4); }}
    h1 {{ margin: 0 0 8px; color:{card_text}; }}
    p  {{ margin: 0 0 20px; color:{card_muted}; }}
    .grid {{ display:grid; gap:14px; grid-template-columns: repeat(auto-fit,minmax(240px,1fr)); margin-top: 12px; }}
    .tile {{ padding:18px; border: 1px solid {border}; background: rgba(255,255,255,0.03); border-radius: 12px; text-decoration:none; display:block; }}
    .tile:hover {{ border-color:{accent}; box-shadow: 0 4px 14px {accent_shadow}; transform: translateY(-1px); }}
    .t1 {{ font-weight:700; color:{card_text}; margin:0 0 6px; }}
    .t2 {{ color:{card_muted}; margin:0 0 10px; }}
    code {{ background: rgba(255,255,255,0.06); color:{accent}; padding: 4px 6px; border-radius:6px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{_b["emoji"]} {_b["name"]}</h1>
    <p>{_b["tagline"]}</p>
    <div style="margin-bottom:20px; padding:20px; border:1px solid {border}; border-radius:14px; background:rgba(19,239,149,0.06); text-align:center;">
      <div style="color:{card_muted}; font-size:13px; margin-bottom:6px;">Call to order</div>
      <a href="tel:+18887628114" style="font-size:32px; font-weight:800; color:{accent}; text-decoration:none; letter-spacing:1px;">+1 (888) 762-8114</a>
    </div>
    <div class="grid">
      <a class="tile" href="/orders">
        <div class="t1">📺 Orders TV</div>
        <div class="t2">Big-screen display (auto-updates)</div>
        <code>/orders</code>
      </a>
      <a class="tile" href="/staff">
        <div class="t1">👨‍🍳 Staff Console</div>
        <div class="t2">Mark orders ready (sends SMS)</div>
        <code>/staff</code>
      </a>
      <a class="tile" href="/orders.json">
        <div class="t1">📋 Orders JSON</div>
        <div class="t2">Recent orders feed</div>
        <code>/orders.json</code>
      </a>
      <div class="tile">
        <div class="t1">☎️ Twilio Voice Webhook</div>
        <div class="t2">TwiML endpoint (Twilio calls this)</div>
        <code>/voice</code>
      </div>
    </div>
  </div>
</body>
</html>"""

@http_router.get("/")
def index():
    return HTMLResponse(_index_html())

# -------------------- Twilio Voice Webhook (TwiML) --------------------

@http_router.post("/voice")
async def voice_twiml(request: Request):
    host, scheme = _host_and_scheme()

    # (Optional) small debug log for your POST body
    try:
        form = await request.form()
        body = "&".join([f"{k}={v}" for k, v in form.items()])
        log_http = os.getenv("LOG_HTTP", "1") not in ("0", "false", "no")
        if log_http:
            print(f"INFO [http] HTTP POST /voice body={body}")
    except Exception:
        form = {}

    call_sid = form.get("CallSid", "unknown")
    from_num = form.get("From", "")
    to_num   = form.get("To", "")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{CONFIG.get("twiml_greeting", "Connecting you now.")}</Say>
  <Connect>
    <Stream url="{scheme}://{host}/twilio">
      <Parameter name="call_sid" value="{call_sid}"/>
      <Parameter name="from" value="{from_num}"/>
      <Parameter name="to" value="{to_num}"/>
    </Stream>
  </Connect>
</Response>"""

    # Some HTTP servers fuss when streaming a long-lived response; return plain XML immediately
    return Response(content=twiml, media_type="text/xml")

# -------------------- JSON APIs --------------------

@http_router.get("/orders.json")
def orders_json(limit: int = 50):
    return JSONResponse(list_recent_orders(limit=limit))

@http_router.get("/orders/in_progress.json")
def orders_in_progress_json(limit: int = 100):
    return JSONResponse(list_in_progress_orders(limit=limit))

# Full order (flavor/addons/etc.)
@http_router.get("/api/orders/{order_no}")
def api_get_order(order_no: str):
    o = get_order(order_no)
    if not o:
        raise HTTPException(404, "Order not found")
    return o

@http_router.get("/api/orders/phone/{order_no}")
def api_get_phone(order_no: str):
    o = get_order(order_no) or {}
    phone = o.get("phone")
    # sms_status is the outcome of the confirmation SMS: sent | failed | skipped
    # | pending. Older records (e.g. /api/seed) only have a phone, so infer.
    status = o.get("sms_status") or ("sent" if phone else "skipped")
    return {
        "order_number": order_no,
        "phone": phone,
        "sms_status": status,
        "sms_reason": o.get("sms_reason", ""),
        "sms_capable": status == "sent",
        "ready_sms": o.get("sms_ready", {}),
    }

@http_router.post("/api/orders/{order_no}/done")
async def api_mark_done(order_no: str):
    ok = set_order_status(order_no, "ready")
    if not ok:
        raise HTTPException(404, "Order not found")

    await publish("orders", {"type": "order_status_changed", "order_number": order_no, "status": "ready"})

    phone = get_order_phone(order_no)
    if not phone:
        # No number on file: the order is still marked ready, the customer
        # picks up by order number. Never block the status change on SMS.
        set_order_sms_status(order_no, "ready", "skipped", "no phone number on file")
        log.warning(f"no phone on file for {order_no} — marked ready, no SMS sent "
                    f"(pickup by order number)")
        return {"ok": True, "sms_sent": False, "reason": "no_phone_on_file"}

    # Twilio's client blocks; keep it off the event loop, which is also
    # carrying live call audio for anyone on the phone right now.
    res = await asyncio.to_thread(send_ready_sms, order_no, phone)
    sms_sent = bool(res.get("ok"))
    reason = "" if sms_sent else (res.get("reason") or "send failed")
    set_order_sms_status(order_no, "ready", "sent" if sms_sent else "failed", reason)
    if sms_sent:
        log.info(f"✅ ready SMS sent for {order_no}")
    else:
        log.warning(f"⚠️  ready SMS failed for {order_no}: {reason} — order is marked ready; "
                    f"tell the customer in person")
    await publish("orders", {"type": "order_sms_status", "order_number": order_no,
                             "which": "ready", "sms_status": "sent" if sms_sent else "failed",
                             "reason": reason})

    # Append to that caller's call log if we still have one
    if append_for_phone:
        latest = append_for_phone(phone, [
            "[ORDER_COMPLETED_BY_STAFF]",
            f"Order Number: {order_no}",
            "Status: ready for pickup",
            "[READY_SMS_SENT]" if sms_sent else "[READY_SMS_FAILED]",
            f"Notification sent to: {phone}" if sms_sent
            else f"No SMS sent ({reason}) — pickup by order number",
        ])
        if latest:
            log.info(f"📝 Logged order completion to: {latest.name}")

    return {"ok": True, "sms_sent": sms_sent, "reason": reason}

# --- DEV seed (optional) ---
@http_router.post("/api/seed")
async def api_seed(n: int = Query(2, ge=1, le=10)):
    created = []
    # Create simple fake orders without touching agent/session/business_logic
    for i in range(n):
        order = {
            "order_number": f"T{datetime.utcnow().strftime('%H%M%S')}{i}",
            "phone": os.getenv("TWILIO_TO_E164", ""),
            "items": [
                {"flavor": CONFIG["menu"]["drinks"][0], "addons": [CONFIG["menu"]["addons"][0]] if CONFIG["menu"].get("addons") else [], "sweetness": CONFIG["defaults"]["sweetness"], "ice": CONFIG["defaults"]["ice"]}
            ],
            "total": 0.0,
            "status": "received",
            "created_at": int(datetime.utcnow().timestamp()),
        }
        add_order(order)
        await publish("orders", {"type": "order_created", "order_number": order["order_number"], "status": "received"})
        created.append(order["order_number"])
    return {"ok": True, "orders": created}

# -------------------- Server-Sent Events (orders bus) --------------------

@http_router.get("/orders/events")
async def orders_events():
    q = await subscribe("orders")

    async def event_gen():
        try:
            while True:
                try:
                    # Wait up to 25s for a real event
                    msg = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {_json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat keeps proxies/browsers from dropping idle SSE
                    yield 'data: {"type":"ping"}\n\n'
        except asyncio.CancelledError:
            pass
        finally:
            await unsubscribe("orders", q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")

# -------------------- UI Pages (Orders TV + Staff Console) --------------------

def _orders_tv_html(refresh: int) -> str:
    t = _theme()
    font = t["font_family"]
    tv_bg = t["orders_tv_bg"]
    tv_card = t["orders_tv_card_bg"]
    tv_border = t["orders_tv_border"]
    tv_text = t["orders_tv_text"]
    accent = t["accent"]
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{CONFIG["brand"]["name"]} - Now Preparing</title>
  {_autorefresh_meta(refresh)}
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin: 0; font-family: {font}; background: {tv_bg}; color:{tv_text}; }}
    header {{ padding: 16px 24px; background: {tv_card}; border-bottom: 1px solid {tv_border}; display:flex; align-items:center; gap:10px; }}
    h1 {{ margin: 0; font-size: 22px; }}
    .muted {{ color:#949498; font-size:12px; margin-left:auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; padding: 24px; }}
    .card {{ background: {tv_card}; border: 1px solid {tv_border}; border-radius: 16px; padding: 24px; text-align: center; box-shadow: 0 1px 8px rgba(0,0,0,0.25); }}
    .ord {{ font-size: 64px; letter-spacing: 2px; font-weight: 900; color: {accent}; }}
  </style>
</head>
<body>
  <header>
    <h1>{CONFIG["brand"]["emoji"]} Now Preparing</h1>
    <div class="muted">Auto refresh: {refresh or 15}s • Live via SSE</div>
  </header>
  <main>
    <div id="grid" class="grid"></div>
  </main>
  <script>
    const grid = document.getElementById('grid');

    function render(list){{
      grid.innerHTML = '';
      if(!list || list.length === 0){{
        const div = document.createElement('div');
        div.style.gridColumn = '1 / -1';
        div.style.color = '#aaa';
        div.style.padding = '80px 16px';
        div.style.textAlign = 'center';
        div.textContent = ' ';
        grid.appendChild(div);
        return;
      }}
      for(const o of list){{
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = '<div class="ord">' + (o.order_number || '----') + '</div>' +
                         '<div style="margin-top:6px;color:#aaa;">' + (o.status || '') + '</div>';
        grid.appendChild(card);
      }}
    }}

    async function load() {{
      const res = await fetch('/orders/in_progress.json', {{ cache: 'no-store' }});
      render(await res.json());
    }}

    function startSSE() {{
      const es = new EventSource('/orders/events');
      es.onopen = () => {{
        // Pull latest state immediately on (re)connect
        load();
      }};
      es.onmessage = (ev) => {{
        try {{
          const msg = JSON.parse(ev.data);
          if (msg.type === 'order_created' ||
              msg.type === 'order_status_changed' ||
              msg.type === 'order_sms_status' ||
              msg.type === 'CallEnded') {{
            load();
          }}
          // ignore 'ping'
        }} catch(e) {{}}
      }};
      es.onerror = () => {{
        // Browser will auto-reconnect; do a one-off reload for safety
        load();
      }};
    }}

    load(); startSSE();
    const REFRESH = {refresh or 15};
    if (REFRESH > 0) setInterval(load, REFRESH * 1000);
  </script>
</body>
</html>"""

def _staff_html(refresh: int) -> str:
    t = _theme()
    accent = t["accent"]
    font = t["font_family"]
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{CONFIG["brand"]["name"]} - Staff Console</title>
  {_autorefresh_meta(refresh)}
  <style>
    :root{{ color-scheme: light dark; }}
    body {{ font-family: {font}; margin:24px; }}
    h1 {{ margin: 0 0 8px; }}
    .muted {{ color:#777; font-size: 12px; margin: 0 0 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }}
    tr:hover {{ background: rgba(0,0,0,0.04); }}
    button {{ padding: 6px 12px; border-radius: 8px; border: 1px solid {accent}; background: {accent}; color: #141E29; font-weight: 600; cursor: pointer; }}
    button:hover {{ opacity: 0.85; }}
    .detail-item {{ margin: 0 0 6px; line-height: 1.25; }}
    .nowrap {{ white-space: nowrap; }}
    .nosms {{ display:block; width:fit-content; margin-top:4px; padding:3px 8px; border-radius:6px;
             font-size:11px; font-weight:700; background:#fde68a; color:#713f12;
             border:1px solid #f59e0b; line-height:1.3; }}
    .nosms.failed {{ background:#fecaca; color:#7f1d1d; border-color:#ef4444; }}
    .nosms.pending {{ background:#e2e8f0; color:#334155; border-color:#94a3b8; }}
    .why {{ display:block; margin-top:2px; font-size:10px; font-weight:600;
           color:inherit; opacity:0.78; }}
    .intl {{ display:inline-block; margin-left:6px; padding:2px 6px; border-radius:5px; font-size:10px;
            font-weight:700; background:rgba(19,239,149,0.18); color:{accent}; border:1px solid {accent};
            letter-spacing:0.5px; vertical-align:middle; }}
  </style>
</head>
<body>
  <h1>{CONFIG["brand"]["emoji"]} Staff Console</h1>
  <p class="muted">Mark orders as done to text the customer that it's ready for pickup. Auto refresh: {refresh or 15}s &bull; Live via SSE</p>

  <table id="tbl">
    <thead>
      <tr>
        <th class="nowrap">Order #</th>
        <th>Phone</th>
        <th>Details</th>
        <th>Status</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>

  <script>
    const tbody = document.querySelector('#tbl tbody');

    function fmtDetails(order) {{
      if (!order || !Array.isArray(order.items) || order.items.length === 0) return '—';
      return order.items.map((it) => {{
        const flavor = it.flavor || 'unknown';
               const addons = (it.addons && it.addons.length) ? it.addons.join(', ') : 'none';
        const sweet = it.sweetness || '50%';
        const ice = it.ice || 'regular ice';
        return `<div class="detail-item"><strong>${{flavor}}</strong><br/><small>${{addons}} • ${{sweet}}, ${{ice}}</small></div>`;
      }}).join('');
    }}

    async function load() {{
      const res = await fetch('/orders/in_progress.json', {{ cache: 'no-store' }});
      const list = await res.json();
      tbody.innerHTML = '';
      for (const o of list) {{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="nowrap"><strong>${{o.order_number}}</strong></td>
          <td data-phone>—</td>
          <td data-details style="color:#777;">Loading…</td>
          <td>${{o.status || ''}}</td>
          <td><button data-done="${{o.order_number}}">Done</button></td>
        `;
        tbody.appendChild(tr);

        // Fill phone
        fetch('/api/orders/phone/' + o.order_number, {{ cache: 'no-store' }})
          .then(r => r.json())
          .then(d => {{
            const cell = tr.querySelector('[data-phone]');
            const esc = (t) => String(t == null ? '' : t).replace(/[&<>"]/g,
              c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
            // international numbers get a marker so staff know delivery may lag
            const intl = (d.phone && !/^\+1\d{{10}}$/.test(d.phone))
              ? '<span class="intl">INTL</span>' : '';
            const num = d.phone
              ? '<span class="nowrap">' + esc(d.phone) + '</span>' + intl : '';
            const why = d.sms_reason ? '<span class="why">' + esc(d.sms_reason) + '</span>' : '';

            // message follows what the confirmation SMS actually did
            if (d.sms_status === 'sent') {{
              cell.innerHTML = num;
            }} else if (d.sms_status === 'failed') {{
              cell.innerHTML = num +
                '<div class="nosms failed">SMS failed — pickup by order number' + why + '</div>';
            }} else if (d.sms_status === 'pending') {{
              cell.innerHTML = num + '<div class="nosms pending">sending text…</div>';
            }} else {{
              cell.innerHTML = num +
                '<div class="nosms">no SMS — pickup by order number' + why + '</div>';
            }}
          }})
          .catch(() => {{ tr.querySelector('[data-phone]').textContent = '—'; }});

        // Fill details
        fetch('/api/orders/' + o.order_number, {{ cache: 'no-store' }})
          .then(r => r.ok ? r.json() : null)
          .then(order => {{
            tr.querySelector('[data-details]').innerHTML = order ? fmtDetails(order) : '—';
          }})
          .catch(() => {{ tr.querySelector('[data-details]').textContent = '—'; }});
      }}
    }}

    tbody.addEventListener('click', async (e) => {{
      const btn = e.target.closest('button[data-done]');
      if (!btn) return;
      const order = btn.getAttribute('data-done');
      btn.disabled = true; btn.textContent = 'Sending...';
      try {{
        const res = await fetch('/api/orders/' + order + '/done', {{ method: 'POST' }});
        if (!res.ok) throw new Error('Failed');
        btn.textContent = 'Sent ✅';
        setTimeout(load, 600);
      }} catch (e) {{
        btn.textContent = 'Error';
      }}
    }});

    function startSSE() {{
      const es = new EventSource('/orders/events');
      es.onopen = () => {{
        // Pull latest state immediately on (re)connect
        load();
      }};
      es.onmessage = (ev) => {{
        try {{
          const msg = JSON.parse(ev.data);
          if (msg.type === 'order_created' ||
              msg.type === 'order_status_changed' ||
              msg.type === 'order_sms_status' ||
              msg.type === 'CallEnded') {{
            load();
          }}
          // ignore 'ping'
        }} catch(e) {{}}
      }};
      es.onerror = () => {{
        // Browser auto-reconnects; do a one-off reload for safety
        load();
      }};
    }}

    load(); startSSE();
    const REFRESH = {refresh or 15};
    if (REFRESH > 0) setInterval(load, REFRESH * 1000);
  </script>
</body>
</html>"""

@http_router.get("/orders")
def orders_tv(refresh: Optional[int] = Query(default=15, ge=0, le=120)):
    # Default to 15s meta+JS refresh; SSE instantly pushes on events (incl. CallEnded)
    return HTMLResponse(_orders_tv_html(refresh or 15))

@http_router.get("/staff")
def staff_console(refresh: Optional[int] = Query(default=15, ge=0, le=120)):
    # Default to 15s meta+JS refresh; SSE instantly pushes on events (incl. CallEnded)
    return HTMLResponse(_staff_html(refresh or 15))

# Keep /barista as a redirect for backwards compatibility
@http_router.get("/barista")
def barista_redirect(refresh: Optional[int] = Query(default=15, ge=0, le=120)):
    from fastapi.responses import RedirectResponse
    url = f"/staff?refresh={refresh}" if refresh else "/staff"
    return RedirectResponse(url=url)
