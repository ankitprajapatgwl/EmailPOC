# EmailPOC

A FastAPI proof-of-concept for managing RFQ (Request for Quotation) email
conversations with suppliers using **dynamic email addressing**, across
**multiple interchangeable email providers** (SendGrid, Mailgun, Elastic
Email).

Each conversation gets a unique email address that encodes the user and
conversation IDs directly in the local-part:

```
usr42_conv3fa9c1b2@mail.yourdomain.com
 ↑         ↑
user_id   conv_id
```

Supplier replies go back to the same address. The active provider's inbound
feature (SendGrid Inbound Parse / Mailgun Routes / Elastic Email inbound
notifications) posts the reply to the single `/webhooks/inbound` endpoint,
which parses both IDs and stores the reply against the correct conversation —
no lookup tables needed on the mail side.

---

## Features

- **Pluggable providers** — switch between SendGrid, Mailgun and Elastic
  Email with a single `EMAIL_PROVIDER` env var. No code changes.
- **Send RFQ emails** from a per-conversation dynamic address.
- **One inbound webhook** for every provider — a factory selects the right
  parser to normalise each provider's payload (and attachments).
- **Track conversations** per user — statuses `open`, `replied`, `declined`.
- **Full conversation thread** view with HTML preview, attachment downloads
  and DKIM/SPF metadata.
- **JSON-backed store** — no database required (`data/db.json`).
- **Single shared logger** with an env-configurable level (`LOG_LEVEL`).
- **Hot-reload** development server via Uvicorn.

---

## Architecture

The application uses the **strategy + factory** pattern on both the outbound
and inbound sides, so providers are swappable and share all common logic.

```
EmailPOC/
├── main.py                       # Entry point — boots Uvicorn (only root file)
├── src/
│   ├── config.py                 # Settings — all env vars in one place
│   ├── logger.py                 # AppLogger — the single shared logger
│   ├── db.py                     # EmailDB — thread-safe JSON store
│   ├── app.py                    # create_app() factory + `app` object
│   ├── route.py                  # HTTP routes only (UI + 1 webhook)
│   ├── services/
│   │   └── conversation_service.py   # Business logic / orchestration
│   ├── email_platform/           # OUTBOUND providers
│   │   ├── email_master.py       # EmailMaster ABC (shared helpers)
│   │   ├── sendgrid_provider.py  # SendGrid SDK
│   │   ├── mailgun_provider.py   # Mailgun HTTP API (requests)
│   │   ├── elasticemail_provider.py  # Elastic Email SDK
│   │   └── factory.py            # EmailProviderFactory
│   └── webhook_factory/          # INBOUND parsers
│       ├── webhook_master.py     # WebhookParserMaster ABC + InboundEmail
│       ├── sendgrid_webhook.py
│       ├── mailgun_webhook.py    # + HMAC signature verification
│       ├── elasticemail_webhook.py
│       └── factory.py            # WebhookParserFactory
├── setup_docs/                   # Per-provider setup guides (DNS, MX, webhook)
│   ├── sendgrid_setup.md
│   ├── mailgun_setup.md
│   └── elasticemail_setup.md
├── templates/                    # Jinja2 UI templates
├── static/                       # Static assets (served at /static)
└── data/
    ├── db.json                   # Auto-created JSON store
    └── attachments/              # Saved inbound email attachments
```

Flow:

```
Browser UI ──(provider API)──▶ Supplier inbox
   │                                  │
   │            reply email           │
   ▼                                  ▼
POST /send                MX ──▶ provider inbound feature
   │                                  │
   ▼                                  ▼  HTTP POST
ConversationService ◀──── POST /webhooks/inbound (one URL, any provider)
   │
   ▼
data/db.json
```

---

## Prerequisites

| Tool                             | Version | Notes                                  |
| -------------------------------- | ------- | -------------------------------------- |
| Python                           | ≥ 3.11  | Union type hints `X \| Y`              |
| [uv](https://docs.astral.sh/uv/) | latest  | Fast Python package manager            |
| A provider account               | —       | SendGrid, Mailgun **or** Elastic Email |
| Domain with DNS control          | —       | Needed for MX + auth records           |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable                      | Required     | Default                           | Description                               |
| ----------------------------- | ------------ | --------------------------------- | ----------------------------------------- |
| `EMAIL_PROVIDER`              | ✅           | `sendgrid`                        | `sendgrid` \| `mailgun` \| `elasticemail` |
| `LOG_LEVEL`                   | ❌           | `INFO`                            | `DEBUG`/`INFO`/`WARNING`/`ERROR`          |
| `INBOUND_DOMAIN`              | ✅           | —                                 | Subdomain whose MX points at the provider |
| `FROM_EMAIL`                  | ✅           | —                                 | Verified sender (From header)             |
| `COMPANY_NAME`                | ❌           | `Your Company`                    | Display name in From + signature          |
| `SENDGRID_API_KEY`            | sendgrid     | —                                 | API key with Mail Send                    |
| `MAILGUN_API_KEY`             | mailgun      | —                                 | Private API key                           |
| `MAILGUN_DOMAIN`              | mailgun      | —                                 | Sending domain                            |
| `MAILGUN_API_BASE`            | ❌           | `https://api.mailgun.net`         | Region base (US/EU)                       |
| `MAILGUN_WEBHOOK_SIGNING_KEY` | ❌           | —                                 | Verifies inbound POSTs (recommended)      |
| `ELASTICEMAIL_API_KEY`        | elasticemail | —                                 | API key with Send access                  |
| `ELASTICEMAIL_API_URL`        | ❌           | `https://api.elasticemail.com/v4` | v4 REST base URL                          |

Only the active provider's credentials are required — the app fails fast at
startup with a clear message if the selected provider is misconfigured.

---

## Provider Setup Guides

Each provider needs domain authentication, MX records for inbound receiving,
and inbound-webhook configuration. Detailed step-by-step guides:

- **SendGrid** → [`setup_docs/sendgrid_setup.md`](setup_docs/sendgrid_setup.md)
- **Mailgun** → [`setup_docs/mailgun_setup.md`](setup_docs/mailgun_setup.md)
- **Elastic Email** → [`setup_docs/elasticemail_setup.md`](setup_docs/elasticemail_setup.md)

---

## Installation & Running

```bash
# 1. Install dependencies (uv creates .venv automatically)
uv sync

# 2. Configure environment
cp .env.example .env
nano .env            # set EMAIL_PROVIDER + that provider's credentials

# 3. Run the hot-reload development server
uv run python main.py
# or directly:
uv run uvicorn src.app:app --host 0.0.0.0 --port 7000 --reload
```

Open **http://localhost:7000** in your browser.

---

## Routes

### UI

| Method | Path                            | Description                  |
| ------ | ------------------------------- | ---------------------------- |
| `GET`  | `/`                             | Send RFQ form                |
| `POST` | `/send`                         | Submit RFQ — create + send   |
| `GET`  | `/tracking`                     | User grid + aggregate stats  |
| `GET`  | `/tracking/{user_id}`           | All conversations for a user |
| `GET`  | `/tracking/{user_id}/{conv_id}` | Full conversation thread     |

### API

| Method | Path                      | Description                              |
| ------ | ------------------------- | ---------------------------------------- |
| `POST` | `/webhooks/inbound`       | Inbound handler (any provider)           |
| `GET`  | `/webhooks/inbound`       | Validation probe (Elastic Email GETs it) |
| `GET`  | `/attachments/{filename}` | Download a saved attachment              |

---

## Development

### Expose localhost to your provider (for webhook testing)

```bash
ngrok http 7000
# Copy the https URL into the provider's inbound webhook config:
#   https://<subdomain>.ngrok-free.app/webhooks/inbound
```

### Simulate an inbound reply (without a real email)

The payload field names differ per provider. Example for **SendGrid**:

```bash
curl -X POST http://localhost:7000/webhooks/inbound \
  -F "from=buyer@acme.com" \
  -F "to=usr42_conv3fa9c1b2@mail.yourdomain.com" \
  -F "subject=RE: RFQ" \
  -F "text=Our price is \$11.50 per unit. MOQ 200 units." \
  -F "spam_score=0.1"
```

See each provider's setup guide for its exact inbound field names.

### Reset the store

```bash
rm data/db.json   # recreated automatically on next request
```
