# API Reference

Complete reference for all HTTP endpoints, WebSocket protocol, and agent functions.

## Base URL

**Production:** `https://voice.boba-demo.deepgram.com`  
**Local:** `http://localhost:8000`

## Public Pages

### GET /

**Landing page with system information**

**Response:** HTML page

- Phone numbers for ordering
- Links to dashboards
- System overview

**Example:**
curl https://voice.boba-demo.deepgram.com/

### GET /orders

**Orders TV Display - Large screen dashboard**

- Shows in-progress orders only
- Designed for display screens

open https://voice.boba-demo.deepgram.com/orders

### GET /barista

**Barista Console - Staff interface**

- Full order details (flavor, toppings, phone)
- "Done" button to mark ready
- Triggers SMS notification

open https://voice.boba-demo.deepgram.com/barista

## API Endpoints

### POST /voice

**Twilio Voice Webhook - Returns TwiML**

**Request:** Form data from Twilio

**Response:** XML (TwiML)

**Example Response:**
```xml
<?xml version="1.0" encoding="UTF-8"?>

**Twilio Configuration:**
- Set as voice webhook in Twilio console
- Method: POST
- Triggers on incoming calls

### GET /orders.json

**Get recent orders as JSON**

**Query Parameters:**
- `limit` (optional): Number of orders to return (default: 50)

**Response:**
[
    "status": "received",
]

# Get last 50 orders

# Get last 10 orders
curl https://voice.boba-demo.deepgram.com/orders.json?limit=10

### GET /orders/in_progress.json

**Get active orders only (status ≠ "ready")**

- `limit` (optional): Number of orders to return (default: 100)

    "status": "received"
    "order_number": "3921",

curl https://voice.boba-demo.deepgram.com/orders/in_progress.json

**Usage:**
- Powers the `/orders` TV display
- Filters out completed orders

### GET /orders/events

**Server-Sent Events stream for real-time updates**

**Response:** `text/event-stream`

**order_created:**
```json
{
  "type": "order_created",
  "order_number": "4782",
  "status": "received"
}
```

**order_ready:**
```json
{
  "type": "order_ready",
  "order_number": "4782",
  "status": "ready"
}
```

**Example (JavaScript):**
const eventSource = new EventSource('/orders/events');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);

  if (data.type === 'order_created') {
    // Refresh order list

**Example (curl):**
curl -N https://voice.boba-demo.deepgram.com/orders/events

### GET /api/orders/{order_no}

**Get full order details by order number**

**Path Parameters:**
- `order_no`: 4-digit order number (e.g., "4782")

  "phone": "+xxxxxxxx",
      "toppings": ["boba", "egg pudding"],
      "addons": ["matcha stencil on top"],
      "price": 7.75
  "total": 7.75,
  "created_at": xxx-xxx-xxxx,
  "name": null

**Error Response (404):**
  "detail": "Order not found"

curl https://voice.boba-demo.deepgram.com/api/orders/4782

### GET /api/orders/phone/{order_no}

**Get phone number for an order**

- `order_no`: 4-digit order number

  "phone": "+xxxxxxxxx"

curl https://voice.boba-demo.deepgram.com/api/orders/phone/4782

### POST /api/orders/{order_no}/done

**Mark order as ready and send SMS notification**

  "ok": true

**Side Effects:**
1. Sets order status to "ready"
2. Publishes "order_ready" event
3. Sends SMS to customer: "Your order #4782 is ready!"

curl -X POST https://voice.boba-demo.deepgram.com/api/orders/4782/done

### POST /api/seed

**Development only - Create test orders**

- `n` (optional): Number of orders to create (default: 2, max: 10)

  "orders": ["4782", "3921"]

# Create 3 test orders
curl -X POST "https://voice.boba-demo.deepgram.com/api/seed?n=3"

**Note:** This endpoint should be disabled or protected in production.

## WebSocket Protocol

### WS /twilio

**Twilio Media Stream WebSocket**

**URL:** `wss://voice.boba-demo.deepgram.com/twilio`

**Protocol:** Twilio Media Streams

### Twilio → Server Messages

**Start Event:**
  "event": "start",
  "start": {
    "streamSid": "MZxxx-xxx-xxxxabcdef",
    "callSid": "CAxxx-xxx-xxxxabcdef",
    "tracks": ["inbound"],
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1

**Media Event:**
  "event": "media",
  "media": {
    "track": "inbound",
    "chunk": "1",
    "timestamp": "xxx-xxx-xxxx",
    "payload": "xxx"

**Stop Event:**
  "event": "stop",
  "streamSid": "MZxxx-xxx-xxxxabcdef"

### Server → Twilio Messages

**Media (Audio Playback):**

**Clear (Interrupt Agent):**
  "event": "clear",

## Agent Functions (Tools)

Functions available to the Deepgram Agent during conversation.

### menu_summary

**Description:** Get menu overview

**Parameters:** None

**Returns:**
  "summary": "We have Taro Milk Tea and Black Milk Tea...",

### add_to_cart

**Description:** Stage a drink (not added until confirmed)

**Parameters:**
- `flavor` (required): "taro milk tea" | "black milk tea"
- `toppings` (optional): Array of toppings
- `sweetness` (optional): "0%" | "25%" | "50%" | "75%" | "100%"
- `ice` (optional): "no ice" | "less ice" | "regular ice" | "extra ice"
- `addons` (optional): Array of add-ons

  "pending_item": {
  "summary": "taro milk tea | boba | no add-ons | 50%, regular ice"

**Error:**
  "ok": false,
  "error": "Topping 'xyz' not available."

### update_pending_item

**Description:** Modify staged drink before confirmation

- `flavor` (optional): Update flavor
- `toppings` (optional): Update toppings
- `sweetness` (optional): Update sweetness
- `ice` (optional): Update ice
- `addons` (optional): Update add-ons

    "flavor": "black milk tea",
    "toppings": ["egg pudding"],
    "sweetness": "75%",
    "ice": "less ice",
  "summary": "black milk tea | egg pudding | no add-ons | 75%, less ice"

### confirm_pending_item

**Description:** Confirm staged drink and add to cart

  "cart_count": 1,
  "item": {
  "cart_total": 6.25

  "error": "No pending drink to confirm."

### clear_pending_item

**Description:** Discard staged drink

  "cleared": true

### order_is_placed

**Description:** Check if order already placed in this call

  "placed": true,
  "order_number": "4782"

### remove_from_cart

**Description:** Remove drink from cart by index

- `index` (required): Zero-based index

  "removed": {
  "cart_count": 0

  "error": "Index out of range.",
  "cart_count": 1

### set_sweetness_ice

**Description:** Update sweetness/ice for last item or by index

- `index` (optional): Item index (default: last item)
- `sweetness` (optional): New sweetness level
- `ice` (optional): New ice level

    "sweetness": "25%",
    "ice": "no ice",

### save_phone_number

**Description:** Save customer's phone number

- `phone` (required): Phone number (any format)

  "phone": "xxx-xxx-xxxx"

**Note:** Automatically normalizes to E.164. Bare 10-digit (or 1+10) input is
assumed to be US (`+1XXXXXXXXXX`); a leading `+` or `00` is honoured as an
explicit country code, so international numbers are accepted as-is
(`+49XXXXXXXXXXX`). Unusable input returns `ok: false` with `phone: null`.

**Returns:** `phone`, plus `international` (true when the number is outside
the US/NANP `+1` range), `last_four_spoken`, and `full_number_spoken` (only
populated for international numbers).

### send_confirmation_text

**Description:** Send the order-confirmation SMS during the call and report the
result, so the agent can tell the customer if it failed. No parameters; call
once after a successful `checkout_order`.

**Returns:** `sms_status` (`sent` | `failed` | `skipped`), `reason`,
`order_number`, and `tell_customer` (what the agent should say). Idempotent —
a repeat call returns `already_sent: true` without sending again.

**SMS outcome fields** (on the stored order, returned by
`GET /api/orders/phone/{order_no}`):

- `sms_status` — `sent` | `failed` | `skipped` | `pending`, the real result of
  the order-confirmation SMS
- `sms_reason` — human-readable cause when not `sent`
- `sms_ready` — `{status, reason}` for the ready-for-pickup SMS
- `sms_capable` — convenience alias for `sms_status == "sent"`

### checkout_order

**Description:** Finalize order and get order number

- `name` (optional): Customer name
- `phone` (optional): Phone number (if not already saved)

  "name": null,

1. Generates 4-digit order number
2. Clears cart
3. Saves to orders.json
4. Publishes "order_created" event
5. Sends SMS: "Your order #4782 is confirmed"

  "error": "Cart is empty."

### order_status

**Description:** Look up order status

- `phone` (optional): Phone number
- `order_number` (optional): Order number

**Returns (found):**
  "found": true,
  "total": 6.25

**Returns (not found):**
  "found": false

**Description:** Extract phone and order number from text

- `text` (required): Free-form text

**Example Input:** "My number is xxx-xxx-xxxx and order 4782"

## Rate Limits

**Current:** No rate limits implemented

**Recommendations for production:**
- API endpoints: 100 requests/minute per IP
- WebSocket: 20 concurrent connections per IP
- SMS: Limited by Twilio account

## Error Responses

### HTTP Errors

**400 Bad Request:**
  "detail": "Invalid parameter"

**404 Not Found:**

**500 Internal Server Error:**
  "detail": "Internal server error"

### Function Call Errors

  "error": "Description of the error"

## Testing

### Test Endpoints

# Health check

# Get orders

# Get specific order

# Mark order ready

### Test SSE

# Follow events

### Test WebSocket

# Install wscat

# Connect

- [Architecture Guide](doc-05-architecture.md)
