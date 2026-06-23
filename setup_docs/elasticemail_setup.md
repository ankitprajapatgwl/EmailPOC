# Elastic Email Setup Guide — EmailPOC RFQ Manager

This is the **Elastic Email** provider guide for **EmailPOC**, a FastAPI RFQ email manager. It is one of three sibling guides (SendGrid, Mailgun, Elastic Email). All three share the same app architecture:

- A **single inbound endpoint**: `POST /webhooks/inbound`.
- A provider switch via the **`EMAIL_PROVIDER`** env var (`sendgrid` | `mailgun` | `elasticemail`).
- **Dynamic per-conversation addresses** encoded in the local-part: `usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}` (e.g. `usr42_conv3fa9c1b2@mail.yourdomain.com`).
- **ngrok** for exposing `localhost:7000` during local development.

To activate Elastic Email, set `EMAIL_PROVIDER=elasticemail` in `.env`.

---

## 1. Overview & Prerequisites

### How EmailPOC uses Elastic Email

| Direction | What happens |
|-----------|--------------|
| **Outbound** | The app sends an RFQ via the Elastic Email v4 REST API. The `From` header = `FROM_EMAIL` (on a verified/authenticated domain). The `Reply-To` header = the dynamic address `usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}`. |
| **Inbound** | A supplier replies to the dynamic `Reply-To` address. The MX for `INBOUND_DOMAIN` points at Elastic Email, which receives the mail, parses it, and HTTP **POSTs form data** to `https://<public-host>/webhooks/inbound`. The app parses the `To`/envelope addresses to recover `user_id` and `conv_id`, then persists the reply and any attachments. |

### Prerequisites

- An **Elastic Email account** on a **PRO plan**. Inbound HTTP notifications are a PRO-only feature: *"This feature is available only for PRO plans."* On free/lower tiers the inbound webhook is unavailable. ([Notification Settings](https://help.elasticemail.com/en/articles/4804685-notification-settings))
- A **domain you control DNS for** (this guide uses the placeholder `yourdomain.com`). You will use a dedicated **subdomain** `mail.yourdomain.com` as `INBOUND_DOMAIN`.
- Local tooling: Python + `uv`, the EmailPOC repo, and **ngrok** for local development.

> **Note — use a dedicated subdomain for inbound.** Point the MX at a subdomain such as `mail.yourdomain.com` rather than the root domain. Otherwise you redirect your main domain's email to Elastic Email. `INBOUND_DOMAIN` must equal the exact (sub)domain whose MX points to `mx.inbound.elasticemail.com`.

---

## 2. Create an API Key

**Console location:** Account **Settings > Manage API Keys**, then **Create**. ([API Settings](https://help.elasticemail.com/en/articles/4799160-api-settings))

1. In your account, go to **Settings > Manage API Keys**.
2. Click **Create** to add a new API key. (You can store up to **15 unique API keys** per account.)
3. **Name** the key and configure **custom permissions** for it. Grant what the app needs — **send email** (full access is also fine). There is **no separate "inbound" API scope**, because inbound is configured via **Notification Settings + MX**, not via a key scope.
4. *(Optional)* Set **Access restrictions** to limit the key to a specific IP address or range (entered in the designated field).
5. Click **Create**.

> **Critical — the key is shown only ONCE.** Elastic Email displays the **96-character GUID** a single time: *"you will not be able to retrieve it once the window is closed."* Afterward, *"the system will obfuscate the key after creation, showing only the last five characters."* Copy it into your `.env` immediately.

**Authentication details** (used by the app's outbound sender):

- Auth header: **`X-ElasticEmail-ApiKey`** (the docs describe the header parameter name as `x-elasticemail-apikey`; HTTP header names are case-insensitive), value = the API key.
- API base URL: **`https://api.elasticemail.com/v4`** (v4 REST API).

---

## 3. Authenticate / Verify Your Sending Domain

**Console:** **Settings > Domains > Manage Domains**, then **Start Verification** (choose **Verify Domain** if you own the domain). After adding the DNS records below, return to this screen and verify. ([How to verify your domain](https://help.elasticemail.com/en/articles/4934400-how-to-verify-your-domain))

> **Note — DNS propagation.** *"New data input in a DNS zone of a domain can take up to 48h to propagate."* The provider's own re-check can also take up to ~24h after the records are visible.

> **Note — verify to lift sending restrictions.** Elastic Email enforces a **"Valid Sender Domain Only"** behavior: mail sent from a domain that is not properly verified is **suppressed**. Verify your sending domain before relying on outbound RFQ delivery. ([Valid Sender Domain Only](https://help.elasticemail.com/en/articles/6044341-valid-sender-domain-only))

Add the following records at your DNS host. Values use the placeholder `yourdomain.com` for the **root-domain** variant.

| Type | Host | Value | Notes |
|------|------|-------|-------|
| SPF (TXT) | `@` (root) | `v=spf1 a mx include:_spf.elasticemail.com ~all` | **Only ONE SPF record per domain.** If you already have one, **merge** by adding `include:_spf.elasticemail.com` to it — do **not** add a second TXT. SPF is mandatory for deliverability. |
| DKIM (TXT) | `api._domainkey` | (see key below) | Selector is **`api`** (host `api._domainkey`). The console shows **your exact** `p=` value — copy it verbatim from your account if it differs from the standard shared key. |
| Tracking (CNAME) | `tracking` | `api.elasticemail.com` | Optional but recommended for open/click tracking. On **Cloudflare** set this to **"DNS Only" (grey cloud, NOT Proxied)**. |
| DMARC (TXT) | `_dmarc` | `v=DMARC1; p=quarantine;` (see note) | Recommended. **Elastic Email strongly recommends `quarantine` or `reject`, NOT `p=none`** (see note below). Requires SPF and/or DKIM passing/aligned first. |

**SPF value (copy verbatim):**

```text
v=spf1 a mx include:_spf.elasticemail.com ~all
```

**DKIM value** for host `api._domainkey.yourdomain.com` (standard Elastic Email shared-domain public key — verify against your console):

```text
k=rsa;t=s;p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCbmGbQMzYeMvxwtNQoXN0waGYaciuKx8mtMh5czguT4EZlJXuCt6V+l56mmt3t68FEX5JJ0q4ijG71BGoFRkl87uJi7LrQt1ZZmZCvrEII0YO4mp8sDLXC8g1aUAoi8TJgxq2MJqCaMyj5kAm3Fdy2tzftPCV/lbdiJqmBnWKjtwIDAQAB
```

> **Note — DMARC policy (per official guidance).** Elastic Email's verification docs explicitly advise: *"We strongly suggest picking option B or C (quarantine or reject) as most large recipient servers tend not to accept emails signed with a lax (none) DMARC record."* You **may** start with `p=none` for an initial monitoring period, but Elastic Email recommends moving to `quarantine`/`reject`. Use the **DMARC Generator** in the console.

**Example DMARC value** for host `_dmarc.yourdomain.com`:

```text
v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com;
```

### Subdomain variant

If you authenticate the **`mail.` subdomain** as the sending/inbound domain instead of the root, use these hosts:

| Record | Host (subdomain variant) |
|--------|--------------------------|
| SPF | `mail` |
| DKIM | `api._domainkey.mail` |
| Tracking | `tracking.mail` |
| DMARC | `_dmarc.mail` |

> **Note — `FROM_EMAIL` vs `INBOUND_DOMAIN`.** `FROM_EMAIL` (e.g. `noreply@yourdomain.com`) must live on an **authenticated** domain (SPF + DKIM). It can be the **root** domain while `INBOUND_DOMAIN` is the **`mail.` subdomain** whose MX points at Elastic Email. The two do not have to be the same domain.

---

## 4. Set Up the Inbound MX Record (most error-prone step)

This is the single most error-prone step — get the hostname exactly right.

**Official instruction:** *"Update your domain's MX Record 'mx.yourdomain.com'. Change it to 'mx.inbound.elasticemail.com'."* ([Notification Settings](https://help.elasticemail.com/en/articles/4804685-notification-settings))

| Type | Host | Value (Mail server) | Priority | Notes |
|------|------|---------------------|----------|-------|
| MX | `mail` (for `mail.yourdomain.com`) — or `@` for the root | `mx.inbound.elasticemail.com` | `10` | Host = the same (sub)domain you set as `INBOUND_DOMAIN`. |

> **Note — priority.** The official docs do **not** specify a numeric priority — they only give the hostname `mx.inbound.elasticemail.com`. Because this should be the **only/primary** MX for the inbound (sub)domain, any priority works; `10` is a conventional default. A single MX with any priority works as long as it is the sole MX for that host.

> **Critical — no competing MX records.** Do **not** keep any other MX (old host, Google Workspace, etc.) on the same inbound subdomain, or mail will be stolen/duplicated and never reach Elastic Email. This is exactly why a **dedicated `mail.` subdomain** is recommended — it isolates inbound RFQ mail from your main domain's email.

Every address `anything@mail.yourdomain.com` (including every `usr*_conv*@mail.yourdomain.com`) then resolves to Elastic Email, giving the **catch-all** behavior the app relies on.

**Verify the MX after propagation** (up to 48h):

```bash
dig MX mail.yourdomain.com +short
# Expect:
# 10 mx.inbound.elasticemail.com.
```

---

## 5. Configure the Inbound Webhook (Notification Settings)

Elastic Email calls this **"Notification Settings" (Inbound notifications)** — **not** a separate "Inbound Parse" product like SendGrid. ([Notification Settings](https://help.elasticemail.com/en/articles/4804685-notification-settings))

**Where:** **Settings** screen > **Notifications** section. Monitor delivery in the account's notification/activity logs.

### Steps

1. Confirm the inbound **MX** for `INBOUND_DOMAIN` points to `mx.inbound.elasticemail.com` (Step 4) and the account is on a **PRO plan**.
2. In **Notifications** settings, set up **Inbound email notifications**. The available route targets are:
   - **"To an HTTP URL"** (e.g. `http://www.somehost.com/can/be/anything`) — **choose THIS one**.
   - **"To an email address"** (e.g. `email@yourdomain.com` — forwards to a mailbox instead).
   - **"Stop"** inbound email notifications (disables forwarding entirely).
3. Set the **Notification URL** to this app's public HTTPS endpoint:

   ```text
   https://<public-host>/webhooks/inbound
   ```

   During local dev, run an ngrok HTTPS tunnel to `localhost:7000` and use that URL, e.g.:

   ```text
   https://<random>.ngrok-free.app/webhooks/inbound
   ```
4. **Save.**

> **Critical — Elastic Email validates the URL with a GET before saving.** Per the docs: *"For validation purposes, the script must accept GET requests and respond with any successful 2xx HTTP status code."* The real inbound payloads arrive as **POST**, but **saving the route requires your endpoint to answer a GET on `/webhooks/inbound` with a 2xx**. The current app only defines `@app.post("/webhooks/inbound")`, so **add a GET handler that returns 200** or saving will fail. For example:
>
> ```python
> @app.get("/webhooks/inbound")
> async def inbound_validation():
>     # Elastic Email pings this with GET to validate the Notification URL.
>     return {"status": "ok"}
> ```

### Catch-all vs specific

- **Catch-all (what this project needs):** Pointing the subdomain MX at Elastic Email captures **any** `anything@INBOUND_DOMAIN`, parses it, and POSTs it to your URL. Every `usr*_conv*@mail.yourdomain.com` then hits the single `/webhooks/inbound` endpoint. No per-address config required.
- **Specific:** You can create multiple role-based routes (`support@`, `sales@`, `info@`) and reorder/stop them individually. **Not needed here** — one HTTP-URL route to `/webhooks/inbound` suffices.

---

## 6. Configure the App's `.env`

Set the provider switch and the Elastic Email keys. Place this in the project root `.env`:

```dotenv
# ── Provider selection ──
EMAIL_PROVIDER=elasticemail

# ── Shared / app-wide ──
LOG_LEVEL=INFO
INBOUND_DOMAIN=mail.yourdomain.com        # subdomain whose MX = mx.inbound.elasticemail.com
FROM_EMAIL=noreply@yourdomain.com          # From header; must be on a verified/authenticated domain
COMPANY_NAME=Acme RFQ

# ── Elastic Email specific ──
ELASTICEMAIL_API_KEY=<your-96-char-api-key>            # sent as X-ElasticEmail-ApiKey header
# Optional / with sensible defaults in code:
ELASTICEMAIL_API_URL=https://api.elasticemail.com/v4   # v4 REST base URL
```

> **Note — addressing invariants.**
> - The dynamic `Reply-To` is built as `usr{user_id}_conv{conv_id}@${INBOUND_DOMAIN}`. `INBOUND_DOMAIN` **must equal** the (sub)domain whose MX points to `mx.inbound.elasticemail.com`.
> - `FROM_EMAIL`'s domain must be authenticated (SPF + DKIM) per Step 3. It may be the root domain while `INBOUND_DOMAIN` is the `mail.` subdomain.

### Outbound send (v4 REST)

The app sends with the v4 REST API using the `X-ElasticEmail-ApiKey` header. For transactional RFQ mail, the correct endpoint is:

```text
POST https://api.elasticemail.com/v4/emails/transactional
```

(`POST /v4/emails` also exists, but `/v4/emails/transactional` is the right call for one-off transactional sends like an RFQ.) `Recipients` is the only strictly required parameter. Set `Content.From = FROM_EMAIL`, `Recipients` = supplier, the body via `Content.Body[]` (with `ContentType: HTML` and the HTML string), and the **`Reply-To` = the dynamic address** via the message's `Content.ReplyTo` / `reply_to` field (or a `Reply-To` entry in `Content.Headers`).

The official Python SDK:

```bash
pip install ElasticEmail
# import ElasticEmail; configure host https://api.elasticemail.com/v4;
# configuration.api_key['apikey'] = <your key>
```
([Python API library](https://elasticemail.com/developers/api-libraries/python) · [PyPI](https://pypi.org/project/ElasticEmail/) · [How to send emails via API](https://help.elasticemail.com/en/articles/2376694-how-to-send-emails-via-api))

---

## 7. Inbound Webhook Payload Field Reference

Elastic Email delivers inbound notifications as **form POST data** (form fields, **NOT JSON**, and **NOT** SendGrid's multipart names). The docs present the payload in `name=value&name=value` form-field style. The app's parser depends on these **exact** field names. ([Notification Settings](https://help.elasticemail.com/en/articles/4804685-notification-settings))

| Purpose | Elastic Email field | Maps to app concept | Notes |
|---------|--------------------|--------------------|-------|
| From (sender email) | `from_email` | app's `from` | |
| From display name | `from_name` | — | |
| Envelope from (SMTP MAIL FROM) | `env_from` | — | |
| Envelope-to list (SMTP RCPT TO) | `env_to_list` | routing recovery | List of recipients. The dynamic address may appear **here**. |
| To header recipients | `to_list` | routing recovery | List. **Parse this** to recover `usr{user_id}_conv{conv_id}@INBOUND_DOMAIN`. |
| Subject | `subject` | subject | |
| Plain-text body | `body_text` | app's `text` | |
| HTML body | `body_html` | app's `html` | |
| Raw headers | `header_list` | header parsing | `"HeaderName: HeaderValue"` lines. Read `Reply-To`, `Message-ID`, `DKIM-Signature`, `Received-SPF` here if needed. |
| Attachment N filename | `att{N}_name` | attachment file name | `att1_name`, `att2_name`, … |
| Attachment N data | `att{N}_content` | attachment bytes | **base64-encoded**. `att1_content`, `att2_content`, … |
| Custom postback headers | (your custom header names) | — | Any custom postback headers you configure are appended as additional fields. |

> **Note — list separators.** The docs do not specify a single canonical delimiter for `to_list` / `env_to_list` / `header_list`. Parse defensively: split on newlines (`\r\n` / `\n`) and, for the recipient lists, also handle comma/semicolon-separated addresses. Do not hard-code one separator.

### Attachments

Attachments are **numbered form fields**, not a JSON array. The docs show the form: `att1_name=attachment_file_name&att1_content=encoded_to_base64_binary_data` (and likewise for `att2_*`, `att3_*`, …):

- `att1_name` / `att1_content`, `att2_name` / `att2_content`, `att3_*`, …
- **Iterate `att{N}_name` / `att{N}_content` (N = 1, 2, 3, …) until none remain** to get both the count and the files. **base64-decode** each `att{N}_content`.
- There is **no separate attachment-count field** documented and **no content-type/metadata field** — infer the content type from the **filename extension**.

### NOT provided by Elastic Email

> **Critical — do NOT expect these (they are SendGrid/Mailgun fields):**
> - No dedicated `spam_score`.
> - No SPF/DKIM **verdict** field.
> - No `charsets` field.
> - No top-level `message_id` field (the Message-ID is inside `header_list`).
> - **No webhook signing/signature field** documented for inbound notifications.
>
> SPF/DKIM results, if present, must be read out of `header_list` (e.g. `Received-SPF`, `Authentication-Results`, `DKIM-Signature`).

> **Critical — secure the endpoint without a signature.** Because the inbound notification carries **no documented HMAC/signature header** (unlike Mailgun/SendGrid), protect `/webhooks/inbound` another way: HTTPS-only + an **unguessable path/secret token** in the URL, or **IP allow-listing**.

### What the app's parser must change for `elasticemail`

The current `dynamic_email.py` inbound handler (`handle_inbound_email`, the `@app.post("/webhooks/inbound")` route) is **SendGrid-shaped** — it reads `data.get("from")`, `data.get("to")`, `data.get("text")`, `data.get("html")`, a numeric `data.get("attachments")` field, `attachment-info` JSON + `attachment{i}` file parts, and `data.get("spam_score")` / `data.get("dkim")` / `data.get("SPF")`. **None of these names exist in the Elastic Email payload.** For `EMAIL_PROVIDER=elasticemail` the handler must instead:

| SendGrid path (current code) | Elastic Email replacement |
|-------------------------|---------------------------|
| `data.get("from")` | `data.get("from_email")` |
| `data.get("to")` | each address in `data.get("to_list")` **and** `data.get("env_to_list")` |
| `data.get("subject")` | `data.get("subject")` (same name) |
| `data.get("text")` | `data.get("body_text")` |
| `data.get("html")` | `data.get("body_html")` |
| `int(data.get("attachments"))` + `attachment-info` JSON + `attachment{i}` file parts | loop `att{N}_name` / `att{N}_content`, **base64-decode** content, infer type from extension |
| `data.get("spam_score")` / `data.get("dkim")` / `data.get("SPF")` | not present — omit, or parse from `header_list` |

> **Note — the current spam-score gate breaks on Elastic Email.** The existing handler computes `float(data.get("spam_score", "0") or "0")` and skips messages with score > 5.0. Since Elastic Email sends no `spam_score`, this always evaluates to 0 (harmless) — but do not rely on it for spam filtering on this provider.

The app's existing To-address regex (in `parse_dynamic_email`):

```python
pattern = rf"usr(\w+)_conv([a-f0-9]{{8}})@{re.escape(INBOUND_DOMAIN)}"
```

must be run against **each** address in `to_list` and `env_to_list` (the dynamic `Reply-To`-derived recipient may land in either list), rather than against a single `to` string.

---

## 8. Test It

### 8.1 Confirm DNS

```bash
dig MX  mail.yourdomain.com +short    # expect: 10 mx.inbound.elasticemail.com.
dig TXT yourdomain.com       +short    # expect your merged SPF: v=spf1 a mx include:_spf.elasticemail.com ~all
dig TXT api._domainkey.yourdomain.com +short   # expect the DKIM k=rsa;t=s;p=... record
```

Then in **Settings > Domains > Manage Domains**, complete verification and confirm the domain shows **verified**.

### 8.2 Start the app + ngrok

```bash
# Terminal 1 — start the app on port 7000
uv run python main.py        # serves dynamic_email:app on localhost:7000

# Terminal 2 — open an HTTPS tunnel to localhost:7000
ngrok http 7000
# copy the https://<random>.ngrok-free.app forwarding URL
```

Set the Elastic Email **Notification URL** to `https://<random>.ngrok-free.app/webhooks/inbound` and **Save** (this triggers the GET validation — your GET handler must return 200).

### 8.3 Verify the validation GET locally

```bash
curl -i https://<random>.ngrok-free.app/webhooks/inbound
# Expect HTTP/1.1 200 OK
```

### 8.4 Send an outbound RFQ

Use the app UI (`http://localhost:7000/`) to send an RFQ. The app sends with `From = FROM_EMAIL` and `Reply-To = usr{user_id}_conv{conv_id}@mail.yourdomain.com`.

### 8.5 Trigger an inbound reply

**Reply** to that RFQ from an external mailbox (e.g. Gmail). The reply goes to the dynamic address at `INBOUND_DOMAIN`; Elastic Email's MX receives it, parses it, and **POSTs form data** to `/webhooks/inbound`.

You can also simulate the POST locally with a form-encoded `curl` (note the base64 attachment fields):

```bash
curl -X POST http://localhost:7000/webhooks/inbound \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "from_email=supplier@example.com" \
  --data-urlencode "from_name=Acme Supplier" \
  --data-urlencode "to_list=usr42_conv3fa9c1b2@mail.yourdomain.com" \
  --data-urlencode "env_to_list=usr42_conv3fa9c1b2@mail.yourdomain.com" \
  --data-urlencode "subject=RE: [RFQ-3FA9] Request for Quotation" \
  --data-urlencode "body_text=Our price is \$11.50 per unit, MOQ 500." \
  --data-urlencode "body_html=<p>Our price is \$11.50 per unit.</p>" \
  --data-urlencode "att1_name=quote.pdf" \
  --data-urlencode "att1_content=JVBERi0xLjQK"
```

### 8.6 What success looks like

- An entry appears in the account's notification/activity log showing a **2xx** POST status.
- The app logs `[Inbound] From: ... → To: ...`, then `Matched → user_id=42, conv_id=3fa9c1b2`, and persists the reply to the conversation.
- The reply shows up in the conversation thread in the tracking UI.

---

## Troubleshooting

> **PRO plan required.** If you see no inbound option or notifications never fire, confirm the account is on a **PRO plan** — inbound HTTP notifications are PRO-only.

> **Wrong / competing MX.** If mail never reaches Elastic Email, run `dig MX mail.yourdomain.com +short` and confirm it returns **only** `10 mx.inbound.elasticemail.com.`. Remove any leftover MX (old host / Google Workspace) on that subdomain — they steal or duplicate delivery.

> **SPF rejected as duplicate.** Only **one** SPF TXT record is allowed per domain. If verification fails, you likely added a second one — **merge** `include:_spf.elasticemail.com` into the existing SPF instead.

> **DMARC `none` may hurt deliverability.** Elastic Email "strongly suggests" `quarantine` or `reject` rather than `p=none`, because many large recipient servers distrust mail under a lax DMARC policy. Use `none` only briefly while monitoring.

> **DNS propagation.** SPF/DKIM/MX changes take **up to 48h** to propagate; Elastic Email's own re-check can take additional time. Re-run the `dig` checks and re-verify in Settings > Domains before testing.

> **Cloudflare proxying.** Set the **tracking CNAME** to **"DNS Only" (grey cloud)** — a proxied (orange) record breaks click tracking. Never proxy MX records.

> **URL validation fails on save.** Elastic Email pings the Notification URL with a **GET** and needs a **2xx** before saving (*"the script must accept GET requests and respond with any successful 2xx HTTP status code"*). If `/webhooks/inbound` only handles POST, add a GET handler returning 200 (see Step 5).

> **Payload looks empty / fields are `None`.** The app may still be reading **SendGrid names** (`from`, `to`, `text`, `html`). For `EMAIL_PROVIDER=elasticemail` it must read `from_email`, `to_list`/`env_to_list`, `subject`, `body_text`, `body_html`, and loop `att{N}_name`/`att{N}_content`. The body is **form-encoded**, not JSON.

> **Address not matched.** The dynamic `usr*_conv*` address may arrive in **`to_list` OR `env_to_list`** (envelope RCPT TO). Run the regex against **both**, splitting each list defensively (newline and comma/semicolon).

> **Attachments missing or corrupt.** There is no documented count field — **loop `att{N}_*` until a name is absent**, and **base64-decode** `att{N}_content`. Content-type is not provided; infer it from the filename extension.

> **ngrok URL changed.** Free ngrok URLs change on every restart. Re-save the Notification URL in Elastic Email each session, or use a **reserved/static** ngrok domain. The app listens on `localhost:7000`. Inspect incoming requests at the ngrok inspector: `http://localhost:4040`.

> **No signature to verify.** Unlike Mailgun/SendGrid, Elastic Email sends **no documented inbound signature header**. Do not attempt HMAC verification. Secure the endpoint with HTTPS + an unguessable path/secret token or IP allow-listing.

> **API key lost.** The 96-char GUID is shown **once**; only the **last 5 chars** are visible afterward. If lost, create a new key (up to 15 per account) and update `ELASTICEMAIL_API_KEY`.

> **Outbound suppressed.** If RFQs never send, confirm `FROM_EMAIL`'s domain is **verified** — Elastic Email suppresses mail from unverified sender domains ("Valid Sender Domain Only").

---

## Sources

- Notification Settings (inbound notifications, MX, payload fields, URL validation, route targets): https://help.elasticemail.com/en/articles/4804685-notification-settings
- How to verify your domain (SPF / DKIM / DMARC / tracking, 48h propagation): https://help.elasticemail.com/en/articles/4934400-how-to-verify-your-domain
- API Settings (96-char GUID, 15 keys, last-5-chars obfuscation, Manage API Keys > Create, permissions, IP restrictions): https://help.elasticemail.com/en/articles/4799160-api-settings
- Valid Sender Domain Only (unverified sender domains suppressed): https://help.elasticemail.com/en/articles/6044341-valid-sender-domain-only
- Importance of SPF and DKIM on your domain: https://help.elasticemail.com/en/articles/6379963-importance-of-spf-and-dkim-on-your-domain
- How to send emails via API (v4 transactional send, reply_to, Content/Body model): https://help.elasticemail.com/en/articles/2376694-how-to-send-emails-via-api
- Python API library: https://elasticemail.com/developers/api-libraries/python
- ElasticEmail on PyPI: https://pypi.org/project/ElasticEmail/
- ElasticEmail Python SDK (GitHub): https://github.com/ElasticEmail/elasticemail-python
- REST API documentation (v4): https://elasticemail.com/developers/api-documentation/rest-api
