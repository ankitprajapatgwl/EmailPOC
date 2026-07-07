# EmailPOC

A FastAPI proof-of-concept for managing RFQ (Request for Quotation) email
conversations with suppliers using **dynamic email addressing**. The
supported and actively-documented providers are **SendGrid** and
**EngageLab**; Mailgun, Elastic Email and SendCloud are also implemented and
selectable via config, but have no written setup guide in this repo.
SendCloud outbound sending is fully implemented; its inbound reply parsing
is a stub (no SendCloud inbound webhook payload doc is available yet).
EngageLab has both outbound sending and inbound reply parsing implemented —
see [`setup_docs/engagelab_guide/engagelab_setup.md`](setup_docs/engagelab_guide/engagelab_setup.md).

Each conversation gets a unique email address that encodes the user and
conversation IDs directly in the local-part:

```
usr42_conv3fa9c1b2@mail.yourdomain.com
 ↑         ↑
user_id   conv_id
```

Supplier replies go back to the same address. The active provider's inbound
feature (SendGrid Inbound Parse / Mailgun Routes / Elastic Email inbound
notifications / EngageLab Inbound Route / SendCloud — not yet implemented)
posts the reply to the single `/webhooks/inbound` endpoint,
which parses both IDs and stores the reply against the correct conversation —
no lookup tables needed on the mail side.

---

## Features

- **SendGrid-first** — domain-level authentication + Inbound Parse, fully
  documented in [`sendgrid_dynamic_domain_auth.md`](sendgrid_dynamic_domain_auth.md).
- **EngageLab** — dynamic sender addresses + Inbound Route webhook, fully
  documented in [`setup_docs/engagelab_guide/engagelab_setup.md`](setup_docs/engagelab_guide/engagelab_setup.md).
- **Pluggable providers** — the code also supports Mailgun, Elastic Email and
  SendCloud via a single `EMAIL_PROVIDER` env var (no code changes), but they
  have no written setup guide in this repo yet. SendCloud inbound reply
  parsing is not implemented (outbound sending only).
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
├── sendgrid_dynamic_domain_auth.md  # Full SendGrid setup guide (DNS, MX, webhook, code)
├── src/
│   ├── config.py                 # Settings — all env vars in one place
│   ├── logger.py                 # AppLogger — the single shared logger
│   ├── db.py                     # EmailDB — thread-safe JSON store
│   ├── app.py                    # create_app() factory + `app` object
│   ├── route.py                  # HTTP routes only (UI + 1 webhook)
│   ├── predefined_users.py       # Seed users shown in the Send RFQ dropdown
│   ├── predefined_projects.py    # Seed projects shown in the Send RFQ dropdown
│   ├── services/
│   │   └── conversation_service.py   # Business logic / orchestration
│   ├── email_platform/           # OUTBOUND providers
│   │   ├── email_master.py       # EmailMaster ABC (shared helpers)
│   │   ├── sendgrid_provider.py  # SendGrid SDK (primary, documented)
│   │   ├── mailgun_provider.py   # Mailgun HTTP API (requests)
│   │   ├── elasticemail_provider.py  # Elastic Email SDK
│   │   ├── sendcloud_provider.py # SendCloud HTTP API (requests)
│   │   ├── engagelab_provider.py # EngageLab HTTP API (requests, Basic Auth)
│   │   └── factory.py            # EmailProviderFactory
│   └── webhook_factory/          # INBOUND parsers
│       ├── webhook_master.py     # WebhookParserMaster ABC + InboundEmail
│       ├── sendgrid_webhook.py
│       ├── mailgun_webhook.py    # + HMAC signature verification
│       ├── elasticemail_webhook.py
│       ├── sendcloud_webhook.py  # Stub — no inbound doc yet
│       ├── engagelab_webhook.py  # EngageLab Inbound Route parser
│       └── factory.py            # WebhookParserFactory
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

| Tool                             | Version | Notes                              |
| -------------------------------- | ------- | ----------------------------------- |
| Python                           | ≥ 3.11  | Union type hints `X \| Y`           |
| [uv](https://docs.astral.sh/uv/) | latest  | Fast Python package manager         |
| A SendGrid account               | —       | Free tier is fine to start          |
| Domain with DNS control          | —       | Needed for domain auth + MX record  |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable                      | Required     | Default                           | Description                                          |
| ----------------------------- | ------------ | --------------------------------- | ----------------------------------------------------- |
| `EMAIL_PROVIDER`              | ✅           | `sendgrid`                        | `sendgrid` \| `mailgun` \| `elasticemail` \| `sendcloud` \| `engagelab` |
| `LOG_LEVEL`                   | ❌           | `INFO`                            | `DEBUG`/`INFO`/`WARNING`/`ERROR`                       |
| `INBOUND_DOMAIN`              | ✅           | —                                 | Subdomain whose MX points at the provider              |
| `FROM_EMAIL`                  | ✅           | —                                 | Verified sender (From header)                          |
| `COMPANY_NAME`                | ❌           | `Your Company`                    | Display name in From + signature                       |
| `SENDGRID_API_KEY`            | sendgrid     | —                                 | API key with Mail Send                                 |
| `MAILGUN_API_KEY`             | mailgun      | —                                 | Private API key                                        |
| `MAILGUN_DOMAIN`              | mailgun      | —                                 | Sending domain                                         |
| `MAILGUN_API_BASE`            | ❌           | `https://api.mailgun.net`         | Region base (US/EU)                                    |
| `MAILGUN_WEBHOOK_SIGNING_KEY` | ❌           | —                                 | Verifies inbound POSTs (recommended)                    |
| `ELASTICEMAIL_API_KEY`        | elasticemail | —                                 | API key with Send access                                |
| `ELASTICEMAIL_API_URL`        | ❌           | `https://api.elasticemail.com/v4` | v4 REST base URL                                        |
| `SENDCLOUD_API_USER`          | sendcloud    | —                                 | API user from the SendCloud console                     |
| `SENDCLOUD_API_KEY`           | sendcloud    | —                                 | API key from the SendCloud console                       |
| `SENDCLOUD_API_BASE`          | ❌           | `https://api.aurorasendcloud.com` | Region base (Singapore/US/HK)                            |
| `ENGAGELAB_API_USER`          | engagelab    | —                                 | API_USER created in the EngageLab dashboard              |
| `ENGAGELAB_API_KEY`           | engagelab    | —                                 | API_KEY generated for that API_USER                      |
| `ENGAGELAB_API_BASE`          | ❌           | `https://email.api.engagelab.cc`  | Region base (Singapore/Turkey)                           |

Only the active provider's credentials are required — the app fails fast at
startup with a clear message if the selected provider is misconfigured.

---

## Provider Setup Guide (SendGrid)

SendGrid is the primary, fully-documented provider. Domain authentication,
the inbound MX record, Inbound Parse webhook configuration and working code
samples are all covered end-to-end in:

- **[`sendgrid_dynamic_domain_auth.md`](sendgrid_dynamic_domain_auth.md)**

It walks through:

1. Authenticating the sending subdomain (domain-level auth, no per-address
   sender verification needed for dynamic addresses).
2. Adding the CNAME records SendGrid generates at your DNS provider.
3. Pointing an MX record at `mx.sendgrid.net` for inbound mail.
4. Configuring the Inbound Parse webhook to POST to `/webhooks/inbound`.
5. Generating dynamic `From`/`Reply-To` addresses and sending/receiving RFQ
   emails end-to-end.

Mailgun, Elastic Email and SendCloud are implemented in
`src/email_platform/` and `src/webhook_factory/` and can be selected via
`EMAIL_PROVIDER`, but none has a written setup guide in this repo yet —
refer to each provider's own docs for domain authentication and inbound
routing if you switch to them. SendCloud specifically only sends outbound
mail today; its `src/webhook_factory/sendcloud_webhook.py` parser is a
stub that raises a clear error until SendCloud's inbound webhook payload
format is documented and implemented.

---

## Provider Setup Guide (EngageLab)

EngageLab is the second fully-documented provider — both outbound sending
(dynamic `from`/`reply_to` addresses) and inbound reply parsing (Inbound
Route webhook) are implemented. The complete walkthrough is in:

- **[`setup_docs/engagelab_guide/engagelab_setup.md`](setup_docs/engagelab_guide/engagelab_setup.md)**

It walks through:

1. Creating a Trigger Email `API_USER`/`API_KEY` pair in the EngageLab
   dashboard and binding it to your sending subdomain.
2. Authenticating the subdomain (SPF/DKIM TXT records + MX record) at your
   DNS provider.
3. Sending with dynamic, unregistered `from`/`reply_to` prefixes once the
   subdomain suffix is verified.
4. Binding an Inbound Route webhook to the `API_USER` so supplier replies
   POST to `/webhooks/inbound`.
5. Testing outbound via `curl` and inbound via `ngrok`.

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

See `sendgrid_dynamic_domain_auth.md` for SendGrid's exact inbound field
names; other providers use different field names for the same data.

### Reset the store

```bash
rm data/db.json   # recreated automatically on next request
```
