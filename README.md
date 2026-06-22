# EmailPOC

A FastAPI-based proof-of-concept for managing RFQ (Request for Quotation) email conversations with suppliers using **dynamic email addressing**.

Each conversation gets a unique email address that encodes the user and conversation IDs directly in the local-part:

```
usr42_conv3fa9c1b2@mail.yourdomain.com
 ↑         ↑
user_id   conv_id
```

Supplier replies go back to the same address. SendGrid's Inbound Parse posts them to the `/webhooks/inbound` endpoint, which parses both IDs and stores the reply against the correct conversation — no lookup tables needed on the MX side.

---

## Features

- **Send RFQ emails** from a per-conversation dynamic address via SendGrid
- **Track all conversations** per user — statuses: `open`, `replied`, `declined`
- **Full conversation thread** view with HTML body preview, attachment downloads, DKIM/SPF metadata
- **JSON-backed store** — no database required, all data in `data/db.json`
- **Light-theme web UI** built with FastAPI + Jinja2
- **Inbound webhook** for receiving and classifying supplier replies
- Hot-reload development server via Uvicorn

---

## Architecture

```
┌─────────────┐    SendGrid API    ┌──────────────────┐
│  Browser UI │ ─────────────────▶ │   Supplier Inbox  │
│  (FastAPI)  │                    └──────────────────┘
│             │                            │
│  GET /      │        Reply email         │
│  POST /send │ ◀── MX → SendGrid ─────────┘
│  GET /track │    Inbound Parse POST
│             │ ─────────────────▶ POST /webhooks/inbound
└─────────────┘                    ↓
      ↓                         EmailDB
   data/db.json ◀───────────────────┘
```

---

## Prerequisites

| Tool                             | Version | Notes                                   |
| -------------------------------- | ------- | --------------------------------------- |
| Python                           | ≥ 3.11  | Union type hints `X \| Y` require 3.10+ |
| [uv](https://docs.astral.sh/uv/) | latest  | Fast Python package manager             |
| SendGrid account                 | —       | Free tier sufficient for POC            |
| Domain with DNS control          | —       | Needed for MX + CNAME records           |

---

## Environment Variables

Copy `.env` and fill in your values:

| Variable           | Required | Default               | Description                                                |
| ------------------ | -------- | --------------------- | ---------------------------------------------------------- |
| `SENDGRID_API_KEY` | ✅       | —                     | API key with **Mail Send** + **Inbound Parse** permissions |
| `INBOUND_DOMAIN`   | ✅       | `mail.yourdomain.com` | Subdomain whose MX record points to SendGrid               |
| `COMPANY_NAME`     | ❌       | `Your Company`        | Display name in outbound email signatures                  |

### SendGrid Setup Checklist

1. **API Key** — [Settings → API Keys](https://app.sendgrid.com/settings/api_keys)  
   Enable _Mail Send (Full Access)_.

2. **Domain Authentication** — [Settings → Sender Authentication](https://app.sendgrid.com/settings/sender_auth)  
   Authenticate `INBOUND_DOMAIN` so SendGrid allows sending _from_ `*@INBOUND_DOMAIN`.  
   Add the provided CNAME records to your DNS.

3. **MX Record** — In your DNS provider, add:

   ```
   Type: MX
   Host: mail          (or whatever your INBOUND_DOMAIN subdomain is)
   Value: mx.sendgrid.net
   Priority: 10
   ```

4. **Inbound Parse Webhook** — [Settings → Inbound Parse](https://app.sendgrid.com/settings/parse)  
   Add a new host:
   ```
   Hostname: mail.yourdomain.com
   URL:      https://yourapp.com/webhooks/inbound  # https://wageless-olga-dottily.ngrok-free.dev/webhooks/inbound
   ```
   During development use [ngrok](https://ngrok.com/) or similar to expose localhost.

---

## Installation & Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd EmailPOC

# 2. Install dependencies (uv creates .venv automatically)
uv sync

# 3. Configure environment
#    Edit .env and fill in SENDGRID_API_KEY and INBOUND_DOMAIN
nano .env
```

---

## Running

```bash
# Hot-reload development server (recommended)
uv run python main.py

# Or directly via uvicorn
uv run uvicorn dynamic_email:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

---

## Project Structure

```
EmailPOC/
├── dynamic_email.py        # FastAPI app — routes, email helpers, webhook
├── db.py                   # Thread-safe JSON store (EmailDB class)
├── main.py                 # Entry point — starts Uvicorn
├── pyproject.toml          # UV/Python project config & dependencies
├── .env                    # Environment variables (secrets — not committed)
│
├── templates/
│   ├── base.html           # Shared layout, sidebar nav, full CSS
│   ├── index.html          # Send RFQ form (GET /)
│   ├── tracking.html       # User grid (GET /tracking)
│   ├── user_conversations.html   # Conversation table (GET /tracking/{user_id})
│   └── conversation_detail.html  # Email thread (GET /tracking/{user_id}/{conv_id})
│
├── static/                 # Static assets (served at /static)
└── data/
    ├── db.json             # Auto-created JSON store
    └── attachments/        # Saved inbound email attachments
```

---

## Routes

### UI

| Method | Path                            | Description                                               |
| ------ | ------------------------------- | --------------------------------------------------------- |
| `GET`  | `/`                             | Send RFQ form                                             |
| `POST` | `/send`                         | Submit RFQ — creates conversation, sends email, redirects |
| `GET`  | `/tracking`                     | User grid with aggregate stats                            |
| `GET`  | `/tracking/{user_id}`           | All conversations for a user                              |
| `GET`  | `/tracking/{user_id}/{conv_id}` | Full conversation thread                                  |

### API

| Method | Path                      | Description                    |
| ------ | ------------------------- | ------------------------------ |
| `POST` | `/webhooks/inbound`       | SendGrid Inbound Parse handler |
| `GET`  | `/attachments/{filename}` | Download a saved attachment    |

### Query Parameters

`GET /tracking/{user_id}/{conv_id}?success=1` — shows a success banner after a new send.  
`GET /?error=<message>` — shows an error banner after a failed send.

---

## DB Schema (`data/db.json`)

```jsonc
{
  "conversations": {
    "<conv_id>": {
      "conv_id": "3fa9c1b2",
      "user_id": "42",
      "supplier_email": "buyer@acme.com",
      "supplier_name": "Acme Corp",
      "email_address": "usr42_conv3fa9c1b2@mail.yourdomain.com",
      "product_name": "Bluetooth Speaker X200",
      "quantity": 500,
      "target_price": "$12.00",
      "subject": "[RFQ-3FA9] Request for Quotation — ...",
      "status": "open | replied | declined",
      "created_at": "2025-06-22T08:00:00+00:00",
      "reply_count": 1,
      "last_reply_at": "2025-06-22T09:15:00+00:00",
      "emails_sent": [
        {
          "from_email": "usr42_conv3fa9c1b2@mail.yourdomain.com",
          "to_email": "buyer@acme.com",
          "subject": "...",
          "body_html": "...",
          "status_code": 202,
          "sent_at": "2025-06-22T08:00:00+00:00",
        },
      ],
      "emails_received": [
        {
          "from_email": "buyer@acme.com",
          "to_email": "usr42_conv3fa9c1b2@mail.yourdomain.com",
          "subject": "RE: [RFQ-3FA9] ...",
          "body_text": "Our price is $11.50 per unit...",
          "body_html": "<p>Our price...</p>",
          "attachments": [
            {
              "filename": "quote.pdf",
              "url": "/attachments/...",
              "size": 48200,
            },
          ],
          "spam_score": "0.1",
          "dkim": "pass",
          "spf": "pass",
          "received_at": "2025-06-22T09:15:00+00:00",
        },
      ],
    },
  },
  "users": {
    "42": ["3fa9c1b2", "a1b2c3d4"],
  },
  "unmatched_emails": [],
}
```

---

## Usage Flow

1. Open **http://localhost:8000**
2. Fill in **User ID**, **Supplier Email**, **Supplier Name**, **Product**, **Quantity**, **Target Price**
3. Click **Send RFQ Email** — the email is sent from `usr{id}_conv{id}@INBOUND_DOMAIN`
4. Supplier replies to that address → SendGrid catches it → posts to `/webhooks/inbound`
5. Check **http://localhost:8000/tracking** to see the reply appear in the conversation thread

---

## Development

### Expose localhost to SendGrid (for webhook testing)

```bash
# Install ngrok, then:
ngrok http 8000
# Copy the https URL and paste it into SendGrid Inbound Parse settings:
# https://abc123.ngrok.io/webhooks/inbound
```

### Simulate an inbound reply (without a real email)

```bash
curl -X POST http://localhost:8000/webhooks/inbound \
  -F "from=buyer@acme.com" \
  -F "to=usr42_conv3fa9c1b2@mail.yourdomain.com" \
  -F "subject=RE: RFQ" \
  -F "text=Our price is \$11.50 per unit. MOQ 200 units." \
  -F "spam_score=0.1"
```

### Reset the store

```bash
rm data/db.json   # deleted on next request — server recreates it automatically
```
