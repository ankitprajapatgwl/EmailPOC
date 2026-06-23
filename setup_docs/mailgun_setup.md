# Mailgun (Sinch) Inbound + Outbound Setup Guide — EmailPOC

This is the **Mailgun** provider guide for **EmailPOC**, a FastAPI RFQ email manager. It is one of three sibling provider guides (SendGrid, Mailgun, Elastic Email). All three share the same app-side contract:

- A single inbound endpoint: **`POST https://<your-public-host>/webhooks/inbound`**
- The active provider is chosen with the **`EMAIL_PROVIDER`** env var (`sendgrid | mailgun | elasticemail`)
- Each conversation gets a **dynamic email address** that encodes routing in the local-part: **`usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}`** (e.g. `usr42_conv3fa9c1b2@mail.yourdomain.com`)
- During local development the public host is an **ngrok** HTTPS tunnel to `localhost:7000`

This guide configures Mailgun end-to-end so that:

- **Outbound:** the app sends RFQ emails with `From = FROM_EMAIL` (a verified sender on your authenticated domain) and `Reply-To = ` the dynamic address.
- **Inbound:** Mailgun receives every message sent to `*@INBOUND_DOMAIN` and HTTP POSTs the parsed message to the single `/webhooks/inbound` endpoint. The app parses the recipient to recover `user_id` and `conv_id`, then saves the body and any attachments.

> **Mailgun terminology note:** Mailgun has **no separate "Inbound Parse" product** (unlike SendGrid). In Mailgun, inbound mail is handled by **Routes** with a **`forward()`** action — routes _are_ the inbound-parse mechanism. ([routes docs](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/routes))

---

## 1. Overview & Prerequisites

You will need:

- A **Mailgun (Sinch) account** — sign up at [mailgun.com](https://www.mailgun.com/).
- A **domain you control DNS for** (the ability to add TXT, CNAME, and MX records at your DNS host). This guide uses the placeholder **`yourdomain.com`**.
- This **EmailPOC** app running locally, listening on **`localhost:7000`**.
- **ngrok** installed for local development (to expose `localhost:7000` over HTTPS).

> **Use a subdomain for email.** Add a subdomain such as `mg.yourdomain.com` (sending) and/or `mail.yourdomain.com` (inbound) rather than the apex `yourdomain.com`, so the parent domain's existing email is unaffected. In this guide `FROM_EMAIL` lives on `mg.yourdomain.com` and `INBOUND_DOMAIN` is `mail.yourdomain.com`. You may also use a single subdomain for both. ([domain verification docs](https://documentation.mailgun.com/docs/mailgun/user-manual/domains/domains-verify))

> **Pick your region first and stick with it.** Mailgun runs separate **US** and **EU** stacks with different base URLs *and* different MX hostnames. US = `https://api.mailgun.net` (default), EU = `https://api.eu.mailgun.net`. Use the base URL matching the region your domain was **created** in — the wrong base URL yields a 401/404 (the docs do not name a specific code, but mismatches surface as not-found / unauthorized errors). ([API overview](https://documentation.mailgun.com/docs/mailgun/api-reference/api-overview))

---

## 2. Create an API Key

This app needs to **send messages**, **manage routes**, and rely on **webhooks**, so create an **Account API key** with full/technical access (not a domain-scoped Sending key).

**Account API key (recommended):** ([RBAC management](https://documentation.mailgun.com/docs/mailgun/user-manual/api-key-mgmt/rbac-mgmt), [API Key Roles](https://help.mailgun.com/hc/en-us/articles/26016288026907-API-Key-Roles), [where to find API keys](https://help.mailgun.com/hc/en-us/articles/203380100-Where-can-I-find-my-API-keys-and-SMTP-credentials))

1. In the Mailgun Dashboard, click your **Profile Menu** (top-right) and open **Account Settings**.
2. Open the **API keys** page.
3. Click **Create key**.
4. In the modal, choose a **Role** (optionally name/describe it):
   - **Admin** — full administrative access across all endpoints. *(Recommended for this setup.)*
   - **Developer** — full Read/Write access to the technical endpoints needed to build and maintain email integrations (Messages, Webhooks, Routes) — sufficient for this app.
   - **Analyst** (read-only access to data and metrics) and **Support** (read access to most endpoints, write only on specific management endpoints) are **insufficient** for sending and route management — do not use these.
5. Click **Create Key** and **copy the secret immediately** — it is shown only once. Store it securely (you will put it in `.env` as `MAILGUN_API_KEY`).

> **Domain Sending key (narrower alternative — not enough here).** Dashboard > **Send > Sending > Domains** > pick domain > **Sending keys** tab > **Add Sending Key**. This only authorizes the `/messages` and `/messages.mime` endpoints for that one domain. It **cannot** create/manage routes or account webhooks, so it is fine for outbound-only but not for this app's full inbound setup. (Routes can also be created in the UI regardless of key.)

**Authentication.** Mailgun's API uses **HTTP Basic Auth** with username `api` and the API key as the password: ([auth docs](https://documentation.mailgun.com/docs/mailgun/api-reference/mg-auth))

```bash
curl --user 'api:YOUR_API_KEY' https://api.mailgun.net/v3/...
```

### 2a. Get the Webhook Signing Key (separate from the API key)

The **HTTP webhook signing key** is **NOT** the API key — it is used to verify the signature on inbound POSTs. ([securing webhooks](https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/securing-webhooks))

1. Click your **Profile Menu** (top-right) > **API Security**.
2. Copy the **HTTP webhook signing key**.
3. You can regenerate it with the refresh / **Reset Key** control if it leaks.

Store it as `MAILGUN_WEBHOOK_SIGNING_KEY` in `.env`.

---

## 3. Authenticate / Verify Your Sending Domain

Add your sending domain in Mailgun, then add the DNS records Mailgun shows you.

1. Go to **Send > Sending > Domains > Add New Domain**. Use a subdomain, e.g. `mg.yourdomain.com`.
2. Mailgun displays the exact records under the domain's **Domain settings > DNS records** (older UI: *Domain Verification & DNS*).
3. Add the records below at your DNS host.

### DNS records to add for sending (`mg.yourdomain.com`)

| # | Type | Host / Name | Value | Notes |
|---|------|-------------|-------|-------|
| 1 | TXT (SPF) | the sending subdomain `mg.yourdomain.com` (Mailgun provisions SPF on the domain you added) | `v=spf1 include:mailgun.org ~all` | Authorizes Mailgun to send. **Only one SPF TXT per host** — if one exists, **merge** the `include:mailgun.org`, don't add a second SPF record. |
| 2 | TXT (DKIM) | selector host shown in panel, e.g. `k1._domainkey.mg.yourdomain.com` (selector varies per domain — copy exactly what the panel shows) | the long `k=rsa; p=MIGfMA0...` public key **from your panel** | **Per-domain value — copy it from the Mailgun panel; never hand-type.** |
| 3 | CNAME (DKIM / Automatic Sender Security) | `pdk1._domainkey.mg.yourdomain.com` and `pdk2._domainkey.mg.yourdomain.com` | `pdk1._domainkey.<id>.dkim1.mailgun.com` / `pdk2._domainkey.<id>.dkim1.mailgun.com` (per-domain target in panel) | **Only if your domain uses Automatic Sender Security** (Mailgun-managed DKIM). Then you add these CNAMEs **instead of** the TXT DKIM in row 2. Two records allow seamless key rotation. ([DKIM security](https://documentation.mailgun.com/docs/mailgun/user-manual/domains/dkim_security)) |
| 4 | CNAME (tracking) | label shown in panel, typically `email.mg.yourdomain.com` | `mailgun.org` | Optional but recommended — enables open/click/unsubscribe tracking. Affects tracking only, not deliverability. |
| 5 | TXT (DMARC) | `_dmarc.yourdomain.com` | `v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com` | **Not auto-provided by Mailgun; optional.** Recommended once SPF+DKIM pass. Start at `p=none`, tighten to `quarantine`/`reject` later. |

Example SPF value:

```dns
v=spf1 include:mailgun.org ~all
```

Example DMARC value:

```dns
v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```

4. Back in the panel, click **Verify DNS Settings**. ([domain verification docs](https://documentation.mailgun.com/docs/mailgun/user-manual/domains/domains-verify))

> **Sending requires SPF + DKIM to pass (green).** The tracking CNAME (row 4) only affects tracking, not the verified/sending state. DNS can take **minutes to 24–48h** to propagate — re-click **Verify** as records appear.

### From vs Reply-To

Set `FROM_EMAIL` to an address on the **authenticated** domain (e.g. `noreply@mg.yourdomain.com`). The app sends with:

- `From = FROM_EMAIL` (e.g. `noreply@mg.yourdomain.com`)
- `Reply-To = ` the dynamic address `usr{id}_conv{cid}@INBOUND_DOMAIN`

so supplier replies route back to the right conversation.

---

## 4. Set Up MX Records for Inbound Receiving

> **This is the most error-prone step. Get the hostnames and the host exactly right.**

Add **two MX records** on the domain/subdomain that will **receive** mail — i.e. on **`INBOUND_DOMAIN`**. In this guide `INBOUND_DOMAIN = mail.yourdomain.com`, so the MX records go on **`mail.yourdomain.com`** (NOT the apex). MX records are what let Mailgun receive and route/store messages for recipients at the domain. ([receive over HTTP](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/receive-http))

### US region (base URL `https://api.mailgun.net`)

| Type | Host / Name | Priority | Value (mail server) |
|------|-------------|----------|---------------------|
| MX | `mail.yourdomain.com` (the `INBOUND_DOMAIN`) | 10 | `mxa.mailgun.org` |
| MX | `mail.yourdomain.com` (the `INBOUND_DOMAIN`) | 10 | `mxb.mailgun.org` |

### EU region (base URL `https://api.eu.mailgun.net`) — use these instead for EU-provisioned domains

| Type | Host / Name | Priority | Value (mail server) |
|------|-------------|----------|---------------------|
| MX | `mail.yourdomain.com` | 10 | `mxa.eu.mailgun.org` |
| MX | `mail.yourdomain.com` | 10 | `mxb.eu.mailgun.org` |

> **Critical gotchas for MX:**
> - Add **BOTH** records — they share the **same priority `10`**.
> - **Do NOT mix US and EU** MX hostnames. Match the region your domain lives in.
> - The host these MX records attach to **must equal `INBOUND_DOMAIN` exactly**. If `INBOUND_DOMAIN = mail.yourdomain.com`, the MX must be on `mail.yourdomain.com`, **not** the apex `yourdomain.com` — otherwise mail to `*@mail.yourdomain.com` never reaches Mailgun.
> - **Remove/avoid any other MX records on that same host** (e.g. a leftover Google Workspace MX). An existing conflicting MX is the usual reason inbound parse "silently" never fires.

---

## 5. Configure the Inbound Route (Mailgun's "Inbound Parse")

In Mailgun, you create a **Route** with a **forward()** action pointing at the single `/webhooks/inbound` URL. ([routes docs](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/routes), [route actions](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/route-actions))

### Console steps

1. Log in to the **Mailgun Control Panel**.
2. Click the **Receiving** tab (routes are configured visually from the Receiving tab, per the docs). Open **Routes**.
3. Click **Create Route** (or **Add Route**).
4. Fill the form fields:
   - **Priority** — an integer; **lower number = higher priority / evaluated first** (routes are evaluated in order of priority, lower numbers first). For a single catch-all webhook, `0` is fine. If you later add specific routes, give them **lower** numbers than the catch-all.
   - **Expression Type** — choose one:
     - **Match Recipient** — a recipient regex. To capture only this app's dynamic addresses: `usr.*_conv.*@mail\.yourdomain\.com` (or broadly `.*@mail\.yourdomain\.com`).
     - **Catch All** — matches every recipient on the domain not matched by a higher-priority route. **Simplest for this POC**, since the app parses the recipient itself.
     - **Custom** — a raw filter expression, e.g. `match_recipient(".*@mail.yourdomain.com")` or `catch_all()`. ([route filters](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/route-filters))
   - **Actions** — enable **Forward** and set the destination to:
     ```
     https://<your-public-host>/webhooks/inbound
     ```
     Custom-action equivalent: `forward("https://<your-public-host>/webhooks/inbound")`. You may add multiple forward targets; you can also add **Store and Notify** (`store(notify="...URL...")`) to retain the raw MIME for **up to 3 days** and POST a retrieval URL instead. ([forwards](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/forwards), [storing & retrieving](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/storing-and-retrieving-messages))
   - **Description** — free text, e.g. `EmailPOC dynamic inbound`.
5. **Save.** (The route's filter and action expressions each have a 4,000-character maximum.)

### Catch-all vs specific

- **`catch_all()` / "Catch All"** — matches any recipient at the domain not matched by a preceding (higher-priority) route. **Best when ONE app owns the whole `INBOUND_DOMAIN`. Recommended here.**
- **`match_recipient(pattern)`** — matches a regex against the SMTP recipient; supports capture groups (numbered `\1`, named `(?P<user>...)` referenced `\g<user>`) that can be injected into the action (e.g. `forward("http://host/post/?mailbox=\1")`). Use when the domain is **shared** or you want to restrict to the `usr..._conv...` pattern. ([route filters](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/route-filters))

### What `forward(URL)` delivers

Mailgun POSTs the **fully parsed message as form fields** (NOT raw MIME). Content-Type is `application/x-www-form-urlencoded` normally, or **`multipart/form-data` when the email has attachments** (attachments arrive as file parts). Only if the forward URL path **ends in `mime` or `raw-mime`** does Mailgun instead send a `body-mime` field with raw MIME and **omit** `body-plain`/`body-html`.

> Keep the path as **`/webhooks/inbound`** (it does **not** end in `mime`) so you receive the parsed fields. The dynamic recipient arrives in the **`recipient`** field, which the app parses to recover `user_id` and `conv_id`. ([receive over HTTP](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/receive-http))

### Local development with ngrok

```bash
ngrok http 7000
```

Copy the **https** forwarding URL and set the route's Forward destination to:

```
https://<id>.ngrok-free.app/webhooks/inbound
```

> **Free ngrok tunnels rotate on each restart.** Update the route's Forward URL whenever the ngrok URL changes.

---

## 6. Configure This App's `.env`

The app selects the provider via `EMAIL_PROVIDER`. For Mailgun:

```dotenv
# ── Provider selector ─────────────────────────────────────────────
EMAIL_PROVIDER=mailgun

# ── Common ────────────────────────────────────────────────────────
LOG_LEVEL=INFO
# Domain whose MX point to Mailgun and that receives dynamic replies.
# MX records (mxa/mxb.mailgun.org, priority 10) must be on THIS host.
INBOUND_DOMAIN=mail.yourdomain.com
# From header for outbound RFQs — an address on your AUTHENTICATED domain.
FROM_EMAIL=noreply@mg.yourdomain.com
COMPANY_NAME=Your Company

# ── Mailgun-specific ──────────────────────────────────────────────
# Account API key (Admin or Developer role). Used with HTTP basic auth
# username "api". Generate at: Account Settings > API keys > Create key.
MAILGUN_API_KEY=YOUR_API_KEY
# The sending domain registered in Mailgun (often same as or parent of
# INBOUND_DOMAIN, e.g. mg.yourdomain.com). Used in the /v3/{domain}/messages path.
MAILGUN_SENDING_DOMAIN=mg.yourdomain.com
# Region base URL: US default, or https://api.eu.mailgun.net for EU domains.
MAILGUN_API_BASE_URL=https://api.mailgun.net
# HTTP Webhook Signing Key (SEPARATE from API key) — used to verify the
# timestamp+token+signature on inbound POSTs. Find at: Profile menu > API Security.
MAILGUN_WEBHOOK_SIGNING_KEY=your-http-webhook-signing-key
```

Notes:

- `MAILGUN_API_KEY` is used for the outbound send call: `POST {MAILGUN_API_BASE_URL}/v3/{MAILGUN_SENDING_DOMAIN}/messages` with basic auth `api:MAILGUN_API_KEY`.
- `MAILGUN_WEBHOOK_SIGNING_KEY` is **NOT** the API key — it is the account **HTTP webhook signing key**. The inbound handler computes `HMAC-SHA256(key=signing_key, msg=timestamp+token)` and compares to the `signature` field.
- `INBOUND_DOMAIN` and `MAILGUN_SENDING_DOMAIN` can be the **same** value (e.g. `mail.yourdomain.com` for both send and receive); split them only if you send from one host and receive on another.

---

## 7. Webhook Payload Field Reference

When the route's `forward()` posts a parsed message to `/webhooks/inbound`, the body is `application/x-www-form-urlencoded` (or `multipart/form-data` when attachments are present). **The parsed-message field names are lowercase and hyphenated** — the app's parser must read these **exact** names. ([receive over HTTP](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/receive-http))

### Core message fields

| App need | Mailgun field | Notes |
|----------|---------------|-------|
| **To (dynamic address)** | `recipient` | The recipient the message was sent to — **this is the dynamic address**; parse it to recover `user_id` / `conv_id`. |
| Envelope sender | `sender` | The SMTP envelope sender (supplier's address). |
| **From** | `from` | The From header (display-name + address). |
| **Subject** | `subject` | The Subject. |
| **Plain body** | `body-plain` | Concatenation of `text/plain` MIME parts. |
| **HTML body** | `body-html` | `text/html` MIME parts. |
| Stripped plain | `stripped-text` | `body-plain` with quoted text + signature removed (may be absent). |
| Stripped HTML | `stripped-html` | HTML with quoted/signature removed (may be absent). |
| Detected signature | `stripped-signature` | The detected signature block (may be absent). |
| All headers | `message-headers` | **JSON-encoded string**, a list of `[name, value]` pairs, order preserved. (Added because not all frameworks handle multi-valued keys.) Parse this for `Message-Id`, `Received-SPF`, `DKIM-Signature`, `Authentication-Results`, `X-Mailgun-Sscore` / `X-Mailgun-Sflag`, etc. |

> Mailgun also flattens many individual headers to top-level form fields on the forward POST (e.g. `From`, `To`, `Subject`, `Message-Id`, `Date`, `Received`, `X-Envelope-From`, `X-Mailgun-Incoming`), but the canonical, framework-safe source for arbitrary headers is `message-headers`.

> **Mailgun does NOT expose dedicated parsed form fields for spam score, SPF result, or DKIM result on the inbound POST.** To get them, read inside `message-headers`:

| App need | Where to read it (inside `message-headers`) |
|----------|---------------------------------------------|
| **Spam score** | `X-Mailgun-Sscore` (numeric, SpamAssassin-style) |
| **Spam flag** | `X-Mailgun-Sflag` (`Yes`/`No`) — present when spam filtering is enabled on the domain (you can also route on it via `match_header('X-Mailgun-Sflag','Yes')`) |
| **SPF result** | the `Received-SPF` header |
| **DKIM / auth result** | the `Authentication-Results` / `DKIM-Signature` headers |
| **Message-Id** | the `Message-Id` header |

### Attachment fields

| App need | Mailgun field | Notes |
|----------|---------------|-------|
| **Attachment count** | `attachment-count` | Number of attachments (string integer). |
| **Attachment files** | `attachment-1`, `attachment-2`, … `attachment-N` | Each attachment is uploaded as a **multipart file part** (filename, content-type, content). Iterate `1` → `attachment-count`. |
| Inline-image mapping | `content-id-map` | JSON string mapping each `Content-ID` header to its attachment field name (for inline images). |

> **Attachments arrive as multipart file parts, not as a JSON field.** Only present when the POST is `multipart/form-data`. Iterate `attachment-1 .. attachment-count` and read the files from the multipart parts.

### Signature / authenticity fields (top-level on the route forward POST)

These top-level form fields appear on the Mailgun POST, including routes/forward and store-notify: ([receive over HTTP](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/receive-http), [securing webhooks](https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/securing-webhooks))

| Field | Meaning |
|-------|---------|
| `timestamp` | Number of seconds passed since January 1, 1970 (Unix epoch). |
| `token` | Randomly generated 50-character string (cache it to block replay). |
| `signature` | Hex HMAC to verify. |
| `parent-signature` | Only present for subaccount events. |

> **Field-shape note:** on **event webhooks** configured under Webhooks, Mailgun nests `timestamp`/`token`/`signature` inside a `signature` JSON object. On **route `forward()` POSTs** (this app's flow), they arrive as **top-level form fields** alongside the parsed message. Read them as top-level form values in the inbound handler.

**Verification algorithm** (the app's `/webhooks/inbound` handler must do this):

```
HMAC-SHA256(
  key = MAILGUN_WEBHOOK_SIGNING_KEY,        # NOT the API key
  msg = timestamp + token                    # concatenated, NO separator, in that order
)
# compare the resulting hex digest to the `signature` field (constant-time compare)
```

Reference (Node, from the docs):

```js
const encodedToken = crypto
  .createHmac('sha256', signingKey)
  .update(timestamp.concat(token))
  .digest('hex');
return encodedToken === signature;
```

> **MIME variant (not used here):** if the forward URL path ended in `mime`/`raw-mime`, Mailgun would send `body-mime` (raw MIME) and **omit** `body-plain`/`body-html`. Because `/webhooks/inbound` does **not** end in `mime`, you receive the parsed fields above.

---

## 8. Test It & Troubleshooting

### Test flow

**1. Verify DNS.** In the panel, **Send > Domains > your domain** should show **SPF + DKIM green ("Verified")**.

**2. Outbound test.** Trigger the app to create a conversation and send an RFQ, or use curl:

```bash
curl -s --user "api:$MAILGUN_API_KEY" \
  https://api.mailgun.net/v3/mg.yourdomain.com/messages \
  -F from='noreply@mg.yourdomain.com' \
  -F to='you@example.com' \
  -F h:Reply-To='usr42_conv3fa9c1b2@mail.yourdomain.com' \
  -F subject='RFQ test' \
  -F text='hello'
```

Success returns JSON with a **queued message id**; check **Send > Logs** for **Accepted/Delivered**.

**3. Inbound test.** From your mailbox, **reply** to that message (the To becomes the dynamic Reply-To `usr42_conv3fa9c1b2@mail.yourdomain.com`), or send a fresh email straight to `usr42_conv3fa9c1b2@mail.yourdomain.com`. Mailgun matches the route and POSTs to `https://<ngrok>/webhooks/inbound`.

**4. What success looks like.** The ngrok inspector (`http://127.0.0.1:4040`) shows an incoming **POST with 200**; app logs show the recipient parsed to `user_id=42`, `conv_id=3fa9c1b2`, the reply saved, and attachments written. **Send > Logs** shows the route matched and the HTTP forward got a **200**.

### Troubleshooting

> **DNS propagation.** SPF/DKIM can take minutes to 48h. Re-click **Verify**. Confirm with `dig TXT mg.yourdomain.com` and `dig MX mail.yourdomain.com`.

> **Wrong/missing MX (most common inbound failure).** Confirm **both** `mxa.mailgun.org` **and** `mxb.mailgun.org` at priority **10** exist on **`INBOUND_DOMAIN`** (not the apex), with **no conflicting MX** (e.g. leftover Google MX). EU domains need `mxa.eu.mailgun.org` / `mxb.eu.mailgun.org`.

> **Route never fires.** Check route **Priority** order — a higher-priority (lower-numbered) `store()`/`stop()` can short-circuit; the `catch_all()` route must be the **lowest-priority (highest-numbered)** so specific routes win first. Verify any recipient regex actually matches `usr..._conv...@INBOUND_DOMAIN` (escape the dots). Check **Send > Logs** for the inbound event and the route match.

> **Signature mismatch (401 from your handler).** Usually caused by using the **API key instead of the HTTP Webhook Signing Key**, wrong concatenation order, or an inserted separator. Correct algorithm: **HMAC-SHA256**, key = **HTTP webhook signing key**, message = `timestamp` **concatenated with** `token` (**no separator, timestamp first**), compare the hex digest to `signature`. The key lives at **Profile menu > API Security**.

> **ngrok.** The free tunnel URL **rotates on every restart** — update the route's Forward URL. Use the **https** URL and the path **`/webhooks/inbound`** (must NOT end in `mime`, or you'd get `body-mime` instead of parsed fields). The app must listen on **7000** to match `ngrok http 7000`.

> **Attachments missing.** Only present when the POST is `multipart/form-data`. Iterate `attachment-1 .. attachment-count` and read the files from the multipart parts — not from a JSON field.

> **Region mismatch (401/404 on send).** Usually means `MAILGUN_API_BASE_URL` doesn't match the domain's region (US `https://api.mailgun.net` vs EU `https://api.eu.mailgun.net`).

> **Replies not routing to the right conversation.** Confirm the outbound send set **`Reply-To`** (not just `From`) to the dynamic address, so the supplier's reply `To` = the dynamic address.

---

## Sources

- Receive (HTTP / inbound parse): https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/receive-http
- Routes: https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/routes
- Route filters: https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/route-filters
- Route actions: https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/route-actions
- Forwards: https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/forwards
- Storing & retrieving messages: https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/storing-and-retrieving-messages
- Domain verification: https://documentation.mailgun.com/docs/mailgun/user-manual/domains/domains-verify
- DKIM security (Automatic Sender Security): https://documentation.mailgun.com/docs/mailgun/user-manual/domains/dkim_security
- API key RBAC management: https://documentation.mailgun.com/docs/mailgun/user-manual/api-key-mgmt/rbac-mgmt
- Authentication: https://documentation.mailgun.com/docs/mailgun/api-reference/mg-auth
- API overview (regions/base URLs): https://documentation.mailgun.com/docs/mailgun/api-reference/api-overview
- Securing webhooks (signature verification): https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/securing-webhooks
- Webhooks: https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/webhooks
- Domain Verification Setup Guide (Help Center): https://help.mailgun.com/hc/en-us/articles/32884700912923-Domain-Verification-Setup-Guide
- Where to find API keys & SMTP credentials: https://help.mailgun.com/hc/en-us/articles/203380100-Where-can-I-find-my-API-keys-and-SMTP-credentials
- API Key Roles: https://help.mailgun.com/hc/en-us/articles/26016288026907-API-Key-Roles
