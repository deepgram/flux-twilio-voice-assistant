# Deepgram Drinks - Voice Ordering System

A production-ready voice ordering system built with **FastAPI**, **Twilio**, and **Deepgram Agent API**. Features real-time voice conversations, SMS notifications, and live order dashboards.

## What is Deepgram Drinks?

Deepgram Drinks is an AI-powered voice ordering system that allows customers to call a phone number and place drink orders through natural conversation. The system uses advanced speech recognition, natural language processing, and text-to-speech to create a seamless ordering experience.

The menu is fully configurable via `app/menu_config.json`, currently set up for an espresso/coffee cart (latte, cappuccino, espresso, americano, macchiato, hot chocolate).

### Key Features

-  **Natural Voice Ordering**: Customers call and speak naturally to place orders
-  **AI-Powered Assistant**: Uses Deepgram's Agent API for intelligent conversation
-  **SMS Notifications**: Automatic order confirmations and ready notifications
-  **Real-time Dashboards**: Live order tracking for staff and customers
-  **Production Ready**: Containerized, scalable, and secure

## Demo

### How It Works

1. **Customer calls** your Twilio phone number
2. **AI greets** them: "Hey! Welcome to Deepgram Drinks. What can I get started for you?"
3. **Natural conversation** - Customer says: "I'd like a latte with vanilla syrup"
4. **AI confirms** order details and asks for phone number
5. **Order placed** - Customer receives SMS confirmation with order number
6. **Staff sees** order on dashboard and prepares it
7. **Ready notification** - Customer gets SMS when order is ready

### Sample Conversation

```
Customer: "Hi, I'd like a cappuccino with soy milk"
AI: "One cappuccino with soy milk. Is that correct?"
Customer: "Yes, that's right"
AI: "Great! Would you like anything else?"
Customer: "No, that's all"
AI: "Can I please get your phone number for this order?"
Customer: "555-123-4567"
AI: "Thank you! Your order number is 4782. We'll text you when it's ready for pickup!"
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Customer      │    │   Twilio Voice   │    │   Your Server   │
│   (Phone Call)  │◄──►│   (Webhook)      │◄──►│   (FastAPI)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Deepgram Agent │
                                               │(STT + LLM + TTS)│
                                               └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Twilio SMS     │
                                               │  (Notifications)│
                                               └─────────────────┘
```

### Core Components

- **FastAPI Backend**: REST API + WebSocket bridge for audio streaming
- **Deepgram Agent**: Real-time speech-to-text, LLM reasoning, text-to-speech
- **Twilio Integration**: Voice calls + SMS notifications
- **Real-time Dashboard**: Server-Sent Events for live order updates
- **Containerized**: Podman/Docker with production-ready configuration

## Quick Start

### Prerequisites

- Python 3.11+
- Podman or Docker (see [Local Container Runtimes](#local-container-runtimes) below)
- ngrok (for local testing)
- Twilio account with A2P 10DLC approval (US registration; this demo is set up
  for a US number — see [Phone Numbers & SMS](#phone-numbers--sms))
- Deepgram API key

### Local Container Runtimes

This project ships two equivalent script pairs — use whichever matches the runtime
you have installed. Both build the same `Containerfile` and publish host port 8000.

| Runtime | Install | Start | Stop |
|---|---|---|---|
| **Colima** (Docker engine, no GUI) | `brew install colima docker` | `colima start` then `./docker-start.sh` | `./docker-stop.sh` |
| **Podman** | `brew install podman` then `podman machine init` | `./podman-start.sh` | `./podman-stop.sh` |

Notes:

- **Docker Desktop is not required**, and its license needs a paid subscription at
  companies over 250 employees or $10M revenue. The `docker` CLI itself is
  Apache-2.0 and free — Colima and Rancher Desktop both supply a free daemon for
  it. `docker-start.sh` never launches a GUI app; it just checks for a reachable
  daemon and prints setup hints if there isn't one.
- **Rancher Desktop** also works with the `docker-*.sh` scripts (free, Apache-2.0)
  if you want a GUI.
- **Both runtimes can be installed side by side** — they use separate VMs and
  separate image stores and don't conflict. Just don't run both containers at
  once, since both publish host port 8000.
- **Leave `DOCKER_HOST` unset.** It silently overrides your docker context, so
  `docker` commands can end up talking to a different runtime than you expect.
  `docker-start.sh` warns you if it's set.

### 5-Minute Setup

```bash
# 1. Clone and setup
git clone <repo-url>
cd flux-twilio-voice-assistant
cp sample.env.txt .env

# 2. Edit .env with your API keys
# - Get Deepgram API key: https://console.deepgram.com/
# - Get Twilio credentials: https://console.twilio.com/

# 3. Start the application (or ./docker-start.sh — see Local Container Runtimes)
./podman-start.sh

# 4. Expose to internet (separate terminal)
ngrok http 8000

# 5. Configure Twilio webhook
# Use ngrok URL: https://your-ngrok-url.ngrok-free.app/voice
```

### Test Your Setup

1. **Call your Twilio number** - You should hear the AI greeting
2. **Place a test order** - Try: "I'd like a latte with vanilla syrup"
3. **Check dashboards** - Visit `http://localhost:8000/orders` and `http://localhost:8000/staff`

### Production Deployment

For production deployment on AWS EC2, see the guides in `documentations/` (note: these were written for the original "BobaRista" deployment and still reference that branding, but the setup steps are the same):

- **[Deployment Guide](documentations/doc-04-deployment.md)** - Complete production setup
- **[AWS EC2 Setup](documentations/doc-02-ec2-setup.md)** - Server configuration
- **[Twilio Setup](documentations/doc-03-twilio-setup.md)** - Phone number configuration
- **[Architecture Guide](documentations/doc-05-architecture.md)** - System design details

## Project Structure

```
flux-twilio-voice-assistant/
├── app/                          # Main application code
│   ├── main.py                   # FastAPI application entrypoint
│   ├── app_factory.py            # Application factory with lifecycle hooks
│   ├── settings.py               # Configuration and environment variables
│   ├── http_routes.py            # REST endpoints (Twilio webhooks, dashboards)
│   ├── ws_bridge.py              # WebSocket bridge for Twilio <> Deepgram audio
│   ├── agent_client.py           # Deepgram Agent API client
│   ├── agent_functions.py        # AI tool definitions and state management
│   ├── business_logic.py         # Core business logic (menu, cart, orders)
│   ├── menu_config.json          # Menu and branding configuration
│   ├── orders_store.py           # Thread-safe JSON persistence layer
│   ├── events.py                 # Pub/sub system for real-time updates
│   ├── audio.py                  # Audio format conversion (u-law <> Linear16)
│   ├── send_sms.py               # Twilio SMS integration
│   ├── session.py                # User session management
│   ├── call_logger.py            # Per-call log files (one file per call)
│   ├── order_ids.py              # Order ID generation utilities
│   └── orders.json               # Order storage (auto-reset on startup)
│
├── logs/                         # One log file per call (bind-mounted, gitignored)
├── documentations/               # Comprehensive documentation
├── Containerfile                 # Podman/Docker build configuration
├── podman-start.sh               # Local development script (Podman)
├── podman-stop.sh                # Cleanup script (Podman)
├── docker-start.sh               # Local development script (Docker/Colima)
├── docker-stop.sh                # Cleanup script (Docker/Colima)
├── requirements.txt              # Python dependencies
├── sample.env.txt                # Environment variables template
└── README.md                     # This file
```

## Technical Details

### Audio Processing Pipeline

1. **Twilio Input**: u-law 8kHz audio from phone calls
2. **Resampling**: Convert to Linear16 48kHz for Deepgram
3. **Deepgram Processing**: STT -> LLM reasoning -> TTS
4. **Output**: Convert back to u-law 8kHz for Twilio

### AI Agent Configuration

- **STT Model**: `flux-general-en` (real-time speech recognition)
- **LLM Model**: `gemini-2.5-flash` (reasoning and responses)
- **TTS Model**: `aura-2-odysseus-en` (natural voice synthesis)
- **Language**: English (`en`)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Landing page |
| `/voice` | POST | Twilio webhook (call initiation) |
| `/twilio` | WS | WebSocket for audio streaming |
| `/orders` | GET | TV dashboard (large display) |
| `/staff` | GET | Staff console interface |
| `/orders.json` | GET | Orders data (JSON API) |

## Environment Configuration

Create `.env` file with required variables:

```bash
# Server Configuration
VOICE_HOST=your-domain.com

# Deepgram API
DEEPGRAM_API_KEY=your_deepgram_key

# Twilio Voice (calls)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_E164=+1234567890
TWILIO_TO_E164=+1234567890

# Twilio SMS (notifications)
MSG_TWILIO_ACCOUNT_SID=your_msg_account_sid
MSG_TWILIO_AUTH_TOKEN=your_msg_auth_token
MSG_TWILIO_FROM_E164=+1234567890

# Agent Configuration
AGENT_LANGUAGE=en
AGENT_TTS_MODEL=aura-2-odysseus-en
AGENT_STT_MODEL=flux-general-en

# Per-call log files (all optional)
CALL_LOG_TO_FILE=1                 # 0 to keep stdout-only logging
CALL_LOG_DIR=/app/logs             # container path; bind-mounted to ./logs
CALL_LOG_LEVEL=INFO                # file-only level; stdout still uses LOG_LEVEL
TZ=America/New_York                # timestamps + log filenames; container default is UTC
```

## Phone Numbers & SMS

> **This setup assumes a US deployment.** The cart has a US phone number, and
> "international" throughout the code and the agent prompt means *not US*
> (anything outside `+1`). Callers from other countries are fully supported —
> their numbers are stored and texted normally — but if you run this demo
> somewhere other than the US, see
> [Running this outside the US](#running-this-outside-the-us) below, because
> that assumption is baked into a handful of places.

Numbers are normalized to E.164 by `normalize_phone()` in
[app/business_logic.py](app/business_logic.py):

| Caller input | Stored as | `international` |
|---|---|---|
| `415 555 1234` (bare digits) | `+14155551234` | false |
| `+14155551234` | `+14155551234` | false |
| `+34628352364` | `+34628352364` | true |
| `0049151226247926` (`00` prefix) | `+49151226247926` | true |
| `+34` / garbage | `null` | — |

An explicit country code always wins: a leading `+` or `00` is never
reinterpreted as a US number, so short foreign numbers (`+45`, `+47`) stay
intact. Bare digits with no country code are assumed to be US, since this is a
US phone line.

**What the agent does with it.** `save_phone_number` returns an
`international` flag, and the prompt branches on it: a US number is read back
by its last four digits with no mention of where it's from, while an
international number is announced as such and read back **in full** (a
misheard country code can't be caught from the last four digits). If no usable
number is available, the agent asks once, then proceeds without one.

**An order is never blocked by a missing phone number.** Registering the order
and sending the SMS are separate steps in `_finalize_and_notify`
([app/ws_bridge.py](app/ws_bridge.py)): the order always reaches the store and
both dashboards, and the SMS is a best-effort follow-up.

**The dashboard message follows what the send actually did.** Each order gets
two SMS attempts — the confirmation when the order is placed, and the pickup
notice when staff hit Done. The confirmation's real outcome is recorded on the
order as `sms_status`, and `/staff` renders from that:

| `sms_status` | Staff console shows | When |
|---|---|---|
| `sent` | just the number (`INTL` chip if international) | Twilio accepted the message |
| `failed` | red **"SMS failed — pickup by order number"** + the reason | Twilio rejected it — bad credentials, no messaging-enabled number, country not enabled, unroutable number |
| `skipped` | amber **"no SMS — pickup by order number"** + the reason | nothing was attempted: no number on file, or the caller never confirmed one |
| `pending` | grey "sending text…" | order registered, send still in flight |

**The agent finds out during the call.** The send happens while the agent can
still speak: after a successful `checkout_order` it calls the
`send_confirmation_text` tool, which sends the text and returns
`sms_status` plus a `tell_customer` instruction. On `failed` or `skipped` the
agent tells the caller it couldn't text them, re-reads the order number
digit-by-digit, and stops promising texts for the rest of the call — including
in its closing line. So the customer hangs up knowing to pick up by order
number, rather than waiting for a text that never arrives.

The tool is idempotent (a second call reports `already_sent`), Twilio's
blocking HTTP client runs via `asyncio.to_thread` so call audio doesn't
stutter, and if the send outruns the 8s tool timeout it is recorded as
`failed — delivery unconfirmed` rather than retried, since a duplicate text is
worse than an unknown outcome. If the agent never calls the tool,
`_finalize_and_notify` still sends at the end of the call as before.

Twilio error codes are translated into something a barista can act on in
[app/send_sms.py](app/send_sms.py) (`_TWILIO_REASONS`) — e.g. a 401 becomes
*"messaging credentials rejected (no messaging-enabled number?)"* and 21408
becomes *"SMS to this country is not enabled on the Twilio account"*. Both
senders return `{"ok", "reason", "sid"}` and never raise, so the outcome is
always recordable. The pickup notice's outcome is stored separately as
`sms_ready` and returned by `/api/orders/phone/{order_no}`.

### Running this outside the US

Nothing here is hard-blocked outside the US, but "home country" is currently
spelled `+1` in several places. To run the cart in, say, Germany — where a
`+49` number is *local* and a `+1` number is the international one — adjust:

| What to change | Where |
|---|---|
| The home-country pattern. `US_E164` (`^\+1\d{10}$`) defines both "valid local number" and, by negation, `is_international()`. Swap in your country's pattern (e.g. `^\+49\d{10,11}$`). | [app/business_logic.py:185](app/business_logic.py:185), [:217](app/business_logic.py:217) |
| The bare-digits fallback. Input with no country code is assumed NANP and gets `+1` prepended. Change to your own country code. | [app/business_logic.py:211](app/business_logic.py:211) |
| The agent's wording. The prompt's CASE A / CASE B branch on `international`, and CASE B says *"you're calling from an international number"* — which reads wrong if the caller is local and *you* are the foreign one. Reword both cases, and the "include the country code if you are outside the US" line in CASE C. | `voice_prompt_template` in [app/menu_config.json](app/menu_config.json) |
| The staff console's `INTL` chip, which tests `/^\+1\d{10}$/` directly rather than asking the API. | [app/http_routes.py:486](app/http_routes.py:486) |
| The hardcoded "Call to order" number on the landing page. | [app/http_routes.py:111](app/http_routes.py:111) |
| `TWILIO_FROM_E164` / `MSG_TWILIO_FROM_E164`, and your Twilio SMS **geo permissions** — these must allow the countries you expect to text, wherever the cart lives. | `.env`, Twilio console |

A cleaner refactor, if you want it properly portable rather than patched: move
the country pattern into `menu_config.json` (alongside `brand` and `limits`)
and have `is_international()` read it, so the prompt and the dashboard can be
phrased as "local" vs. "foreign" instead of "US" vs. "international".

## Per-Call Log Files

Alongside the container's stdout logging, every call gets its own file in
`./logs` on the host (bind-mounted to `/app/logs` in the container by
`podman-start.sh` / `docker-start.sh`):

```
logs/15551234567_20260828-151548_a1b2c3d4.log
     └─ caller digits  └─ start time  └─ CallSid tail
```

The caller-digits prefix means you can find a caller's most recent call with
`ls logs/15551234567_*.log`. Timestamps are container-local — the container
defaults to UTC, so set `TZ` in `.env` if you'd rather read them in your own
timezone. Each file holds everything the app logged while
handling that call — agent events, transcript lines, tool calls and results,
SMS sends, errors — plus a header and a footer:

```
================================================================================
CALL START   2026-08-28T15:15:48
call_sid     CAxxxxxxxx
stream_sid   MZxxxxxxxx
caller       +15551234567
================================================================================
2026-08-28 15:15:49 INFO [ws_bridge] [CAxxxxxxxx] Agent: {"type":"ConversationText",...}
2026-08-28 15:15:52 INFO [ws_bridge] [CAxxxxxxxx] 🔧 function.call add_drink({...})
2026-08-28 15:16:04 INFO [send_sms] [CAxxxxxxxx] 📱 SMS (received) to +1555…: order 1234
================================================================================
CALL END     2026-08-28T15:16:05
duration     17.2s
order        1234
caller       +15551234567
confirmed    True
sms_sent     True
================================================================================
```

When staff later hit **Done** in `/staff`, the ready-for-pickup notification is
appended to that caller's most recent call log too.

Concurrent calls stay separate: each websocket connection is tagged in its own
async context, and a call's log file only accepts records emitted inside it —
including from the background tasks that call spawns. If the logs directory
can't be created or written, the app logs one warning and keeps running.

Useful greps:

```bash
tail -f logs/*.log                      # follow whatever is on the line now
grep -l "order        1234" logs/*.log  # which call produced order 1234
grep -h "ConversationText" logs/1555*.log  # one caller's transcript lines
```


## International Callers

The `"international"` sentinel is gone — real international numbers are now
stored and texted. See [Phone Numbers & SMS](#phone-numbers--sms) above.


## Monitoring & Debugging

Substitute `docker` for `podman` throughout if you're using the Docker scripts —
the container name is `dg-drinks` either way.

```bash
# View application logs
podman logs -f dg-drinks

# View specific log levels
podman logs dg-drinks | grep ERROR
```

## Troubleshooting

**Call not connecting?**
- Check if ngrok is running: `curl https://your-ngrok-url.ngrok-free.app/voice`
- Verify Twilio webhook URL is correct and uses HTTPS
- Check application logs: `podman logs -f dg-drinks`

**No audio on call?**
- Ensure WebSocket URL uses `wss://` (not `ws://`)
- Check Deepgram API key is valid
- Verify `VOICE_HOST` matches your ngrok URL exactly

**SMS not sending?**
- Verify Twilio SMS credentials in `.env`
- Check phone number has SMS capability
- Review Twilio logs in console

```bash
# Restart application (or ./docker-stop.sh && ./docker-start.sh)
./podman-stop.sh && ./podman-start.sh

# Test endpoints
curl http://localhost:8000/orders.json
```
