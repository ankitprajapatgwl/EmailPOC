# Twilio SendGrid Inbound + Outbound Setup Guide — EmailPOC

This is the **SendGrid** provider guide for **EmailPOC**, a FastAPI RFQ email manager. It is one of three sibling provider guides (SendGrid, Mailgun, Elastic Email). All three share the same app-side contract:

- A single inbound endpoint: **`POST https://<your-public-host>/webhooks/inbound`**
- The active provider is chosen with the **`EMAIL_PROVIDER`** env var (`sendgrid | mailgun | elasticemail`) — set **`EMAIL_PROVIDER=sendgrid`** to use this guide.
- Each conversation gets a **dynamic email address** that encodes routing in the local-part: **`usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}`** (e.g. `usr42_conv3fa9c1b2@mail.yourdomain.com`)
- During local development the public host is an **ngrok** HTTPS tunnel to `localhost:7000`

This guide configures SendGrid end-to-end so that:

- **Outbound:** the app sends RFQ emails with `From = FROM_EMAIL` (a verified Single Sender or an address on your authenticated domain) and `Reply-To =` the dynamic address.
- **Inbound:** SendGrid **Inbound Parse** receives every message sent to `*@INBOUND_DOMAIN`, parses it, and HTTP POSTs the parsed fields as `multipart/form-data` to the single `/webhooks/inbound` endpoint. The app parses the recipient (`to`) to recover `user_id` and `conv_id`, then saves the body and any attachments.

> **Two independent SendGrid features.** Outbound uses the **Mail Send** API + a verified sender. Inbound uses **Inbound Parse** + an **MX** record. They are configured separately and do not depend on each other, but both rely on DNS you control.

---

## 2. Overview & Prerequisites

You will need:

- A **Twilio SendGrid account** — sign up at [sendgrid.com](https://sendgrid.com/). (SendGrid is now part of Twilio; the console lives at `app.sendgrid.com`.)
- A **domain you control DNS for** (the ability to add CNAME, TXT, and MX records at your DNS host). This guide uses the placeholder **`yourdomain.com`**.
- This **EmailPOC** app running locally, listening on **`localhost:7000`**.
- **ngrok** installed for local development (to expose `localhost:7000` over HTTPS).

> **Use a subdomain for inbound mail.** Point inbound at a dedicated subdomain such as `mail.yourdomain.com` rather than the apex `yourdomain.com`, so the parent domain's existing email is unaffected. In this guide `INBOUND_DOMAIN = mail.yourdomain.com`. ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))

| Direction | What happens |
|-----------|--------------|
| **Outbound** | The app sends an RFQ via the SendGrid Mail Send API. `From = FROM_EMAIL` (verified sender / authenticated domain). `Reply-To =` the dynamic address `usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}`. |
| **Inbound** | A supplier replies to the dynamic `Reply-To` address. The MX for `INBOUND_DOMAIN` points at `mx.sendgrid.net`; SendGrid receives the mail, parses it, and POSTs `multipart/form-data` to `https://<public-host>/webhooks/inbound`. The app parses `to` to recover `user_id` / `conv_id`, then persists the reply and attachments. |

---

## 3. Create an API Key

The app sends outbound RFQ email through the SendGrid Mail Send API, so it needs an API key with the **Mail Send** scope. (Inbound Parse does **not** use an API key — it is driven by DNS + the console Inbound Parse setting.)

**Console location:** **Settings > API Keys > Create API Key**. ([API keys docs](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys))

1. In the SendGrid console left nav, go to **Settings > API Keys**.
2. Click **Create API Key**.
3. Give it a **name** (e.g. `EmailPOC`).
4. Choose a permission level:
   - **Full Access** — access to all (`GET`/`POST`/`PUT`/`PATCH`/`DELETE`) endpoints. Simplest for a POC.
   - **Restricted Access** (a.k.a. "Custom Access") — recommended for least privilege. Expand **Mail Send** and set it to **Full Access**. That single scope is all this app needs to send. Leave everything else at **No Access**.
   - **Billing Access** — not needed here.
5. Click **Create & View** and **copy the key immediately**.

> **The key is shown only ONCE.** SendGrid: *"You will only be shown your API key one time. Please store it somewhere safe as we will not be able to retrieve or restore it."* Paste it into `.env` as `SENDGRID_API_KEY` right away. ([API keys docs](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys))

The key always begins with the `SG.` prefix. The app authenticates with the standard `Authorization: Bearer <SENDGRID_API_KEY>` header (handled by the SendGrid SDK).

---

## 4. Authenticate / Verify Your Sending Domain

Outbound mail needs a verified sender identity for the `From` header. You have two options:

- **Single Sender Verification** — quickest for a POC (one address, no DNS). Section **4a**.
- **Domain Authentication** — recommended for production; lets you send `From` *any* address on the domain and improves deliverability. Section **4b**.

> **From vs Reply-To.** Whichever you pick, set `FROM_EMAIL` to the verified address (or any address on the authenticated domain). The app always sends `From = FROM_EMAIL` and `Reply-To =` the dynamic `usr{id}_conv{cid}@INBOUND_DOMAIN`, so supplier replies route back to the right conversation.

### 4a. Single Sender Verification (quick POC alternative)

**Console:** **Settings > Sender Authentication > Single Sender Verification > Verify a Single Sender** (then **Create New Sender**). ([Sender Verification](https://www.twilio.com/docs/sendgrid/ui/sending-email/sender-verification))

1. Go to **Settings > Sender Authentication** and, under **Single Sender Verification**, click **Verify a Single Sender / Create New Sender**.
2. Fill the required fields:
   - **From Name** — human-readable name shown to recipients (e.g. your `COMPANY_NAME`).
   - **From Email Address** — the address you will send as; this is your `FROM_EMAIL`. SendGrid emails the verification link here.
   - **Reply To** — can be the same as From (the app overrides `Reply-To` per message anyway).
   - **Company Address, City, State, Zip Code, Country** — required (CAN-SPAM physical address).
   - **Nickname** — internal label only; recipients never see it.
3. Click **Create**, then open the inbox of the **From Email Address** and click the verification link.

> **Single Sender caveats.** SendGrid warns against using large free-inbox addresses (Gmail/Yahoo/Outlook) because *"Messages from this domain might fail a DMARC check."* Use an address on a domain you control. If no verification email arrives within an hour, confirm the From address is valid and re-send. Senders on an already-authenticated domain are auto-verified. ([Sender Verification](https://www.twilio.com/docs/sendgrid/ui/sending-email/sender-verification))

### 4b. Domain Authentication (recommended for production)

**Console:** **Settings > Sender Authentication > Authenticate Your Domain**. Pick your DNS host and the domain (e.g. `yourdomain.com`), keep **Automated Security ON** (the default), and SendGrid generates the CNAME records below. ([Domain Authentication](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication))

With **Automated Security ON** (recommended — SendGrid manages DKIM/SPF for you via CNAMEs), SendGrid generates the following. **The exact hostnames/targets are unique to your account — copy them from the console; the table shows the pattern, not literal values.**

| # | Type | Host / Name (pattern) | Value / Target (pattern) | Notes |
|---|------|-----------------------|--------------------------|-------|
| 1 | CNAME | `em####.yourdomain.com` (the `em` number is account-specific) | `u########.wl###.sendgrid.net` | Mail routing + SPF. Copy the exact `em####` and target from the console. |
| 2 | CNAME | `s1._domainkey.yourdomain.com` | `s1.domainkey.u########.wl###.sendgrid.net` | DKIM key 1 (SendGrid-managed). |
| 3 | CNAME | `s2._domainkey.yourdomain.com` | `s2.domainkey.u########.wl###.sendgrid.net` | DKIM key 2 (allows seamless key rotation). |
| 4 | TXT | `_dmarc.yourdomain.com` | `v=DMARC1; p=none;` | DMARC policy SendGrid suggests. **Optional but recommended.** Start at `p=none`, tighten to `quarantine`/`reject` later. Only **one** `_dmarc` TXT per domain — merge if one exists. |

Example DMARC value:

```dns
v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```

After adding the records, return to the console and click **Verify**.

> **Automated Security uses CNAMEs with underscores.** If your DNS host **rejects underscores in CNAME records**, turn Automated Security OFF; SendGrid then issues an MX + three TXT records you maintain manually instead. ([Domain Authentication](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication))

> **Link Branding (optional).** **Settings > Sender Authentication > Link Branding** adds **two more CNAMEs** (pointing at SendGrid's link-tracking infrastructure) so click/open tracking links use your domain instead of `sendgrid.net`. Not required for EmailPOC. ([Domain Authentication](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication))

> **Avoid an Automated-Security ↔ Inbound MX loop.** If you authenticate the **same** (sub)domain that you also use as `INBOUND_DOMAIN`, you must turn **Automated Security OFF** for it — otherwise SendGrid's CNAME and the inbound MX can form an **infinite bounce loop**. The cleanest setup keeps them separate: authenticate `yourdomain.com` for sending, and use a **distinct** subdomain `mail.yourdomain.com` for inbound (Section 5). ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))

---

## 5. Set Up the Inbound MX Record

> **This is the most error-prone step. Get the host, value, and priority exactly right.**

For SendGrid to receive mail at `*@INBOUND_DOMAIN`, add **one MX record** on the **`INBOUND_DOMAIN`** subdomain (here `mail.yourdomain.com`), pointing at SendGrid's inbound server. ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))

| Type | Host / Name | Priority | Value (mail server) |
|------|-------------|----------|---------------------|
| MX | `mail.yourdomain.com` (the `INBOUND_DOMAIN`) | `10` | `mx.sendgrid.net` |

```dns
mail.yourdomain.com.   MX   10   mx.sendgrid.net.
```

The official instruction: *"Set the **mail server address** to `mx.sendgrid.net`. If your provider offers a field for priority, type `10` before the mail server address."* ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))

> **Critical gotchas for MX:**
> - **Value = `mx.sendgrid.net`** (note `.net`), **priority = `10`**. There is only **one** SendGrid inbound MX host (unlike Mailgun's mxa/mxb pair).
> - The host the MX attaches to **must equal `INBOUND_DOMAIN` exactly**. If `INBOUND_DOMAIN = mail.yourdomain.com`, the MX must be on `mail.yourdomain.com`, **not** the apex `yourdomain.com` — otherwise mail to `*@mail.yourdomain.com` never reaches SendGrid.
> - **Remove/avoid any other MX record on that same host** (e.g. a leftover Google Workspace MX). A conflicting MX is the usual reason inbound "silently" never fires.
> - Some DNS hosts auto-append the zone — entering `mail` may already mean `mail.yourdomain.com`. Verify the final FQDN with `dig MX mail.yourdomain.com`.

---

## 6. Configure Inbound Parse

Tell SendGrid where to POST parsed inbound mail.

**Console:** **Settings > Inbound Parse > Add Host & URL**. ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))

1. Go to **Settings > Inbound Parse** and click **Add Host & URL**.
2. **Receiving Domain** — enter the subdomain (the `mail` part) and select your domain (`yourdomain.com`) from the dropdown, so the receiving domain is **`mail.yourdomain.com`** (= `INBOUND_DOMAIN`).
3. **Destination URL** — set it to your public, internet-accessible endpoint:
   ```
   https://<your-public-host>/webhooks/inbound
   ```
   For local development this is your ngrok HTTPS URL, e.g. `https://<id>.ngrok-free.app/webhooks/inbound`.
4. **Options (checkboxes):**
   - **Check incoming emails for spam** — **enable this.** It runs SpamAssassin on messages ≤ 2.5 MB and adds `spam_score` + `spam_report` to the POST. The app reads `spam_score`. ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))
   - **POST the raw, full MIME message** — **leave this OFF.** Off = SendGrid sends the **parsed** fields (`from`, `to`, `subject`, `text`, `html`, `attachments`, etc.) that the app's parser expects. On = SendGrid sends a single raw `email` MIME blob instead, which this app does **not** parse. ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))
5. Click **Add**.

> **Raw vs parsed — get this right.** With "POST the raw, full MIME message" **OFF** you receive the individual parsed fields in Section 8 (this is what EmailPOC's `SendGridWebhookParser` reads). With it **ON**, attachments and message are URL-encoded into a single `email` field and the parsed `text`/`html`/`attachmentX` fields are **not** sent — the app would see empty bodies. Keep it OFF.

> **Destination URL must be HTTPS and reachable.** SendGrid POSTs from the public internet; `localhost` is not reachable. Use the ngrok HTTPS URL during development (Section 9).

### Local development with ngrok

```bash
ngrok http 7000
```

Copy the **https** forwarding URL and set the Inbound Parse **Destination URL** to:

```
https://<id>.ngrok-free.app/webhooks/inbound
```

> **Free ngrok tunnels rotate on each restart.** Update the Inbound Parse Destination URL in the console whenever the ngrok URL changes.

---

## 7. Configure This App's `.env`

The app selects the provider via `EMAIL_PROVIDER`. For SendGrid:

```dotenv
# ── Provider selector ─────────────────────────────────────────────
EMAIL_PROVIDER=sendgrid

# ── Common ────────────────────────────────────────────────────────
LOG_LEVEL=INFO
# Domain whose MX points to mx.sendgrid.net and that receives dynamic replies.
# The Inbound Parse MX (mx.sendgrid.net, priority 10) must be on THIS host.
INBOUND_DOMAIN=mail.yourdomain.com
# From header for outbound RFQs — a verified Single Sender, or any address on
# your AUTHENTICATED domain.
FROM_EMAIL=noreply@yourdomain.com
COMPANY_NAME=Your Company

# ── SendGrid-specific ─────────────────────────────────────────────
# API key with the Mail Send scope. Begins with "SG.". Shown only once —
# generate at: Settings > API Keys > Create API Key.
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxx.yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
```

Notes:

- `SENDGRID_API_KEY` is the **only** SendGrid credential the app needs. Inbound Parse is authenticated by DNS ownership + the console setting, **not** by an API key.
- `INBOUND_DOMAIN` must exactly match the **Receiving Domain** you set in Inbound Parse (Section 6) and the host of the MX record (Section 5).
- `FROM_EMAIL` must be a verified Single Sender (4a) or live on the authenticated domain (4b).

---

## 8. Inbound Webhook Payload Field Reference

When "POST the raw, full MIME message" is **OFF**, SendGrid POSTs `multipart/form-data` to `/webhooks/inbound` with the fields below. The app's `SendGridWebhookParser` reads the **bold** ones (note the exact capitalization — `SPF` and `dkim`). ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook), [Inbound Email](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/inbound-email))

| App need | SendGrid field | Meaning |
|----------|----------------|---------|
| **From** | **`from`** | The email sender extracted from the message headers. |
| **To (dynamic address)** | **`to`** | The recipient extracted from the message headers — **this is the dynamic address**; parse it to recover `user_id` / `conv_id`. |
| **Subject** | **`subject`** | The subject line of the email message. |
| **Plain body** | **`text`** | The text-formatted (`text/plain`) email body. |
| **HTML body** | **`html`** | The HTML-formatted (`text/html`) email body, if provided. |
| **Spam score** | **`spam_score`** | The SpamAssassin rating (string, e.g. `"0.5"`). **Present only when "Check incoming emails for spam" is enabled.** |
| **SPF result** | **`SPF`** | Result of SPF verification of the sender + receiving IP. **(Capital `SPF`.)** |
| **DKIM result** | **`dkim`** | Verification results of DKIM / domain-keys signatures. **(lowercase `dkim`.)** |
| **Attachment count** | **`attachments`** | Number of attachments included (string integer). |
| **Attachment metadata** | **`attachment-info`** | JSON object with one entry per attachment (`filename`, `type`, `content-id`). The app reads `filename` and `type` per `attachmentN`. |
| **Attachment files** | **`attachment1`, `attachment2`, … `attachmentN`** | Each attachment uploaded as a **multipart file part**. The app iterates `1 .. attachments`. |
| (also sent) | `headers` | The raw headers of the email. |
| (also sent) | `envelope` | JSON SMTP envelope: `{"to":["..."],"from":"..."}` (envelope recipient + return-path). |
| (also sent) | `charsets` | JSON map of each field name to its character set (SendGrid converts headers to UTF-8). |
| (also sent) | `sender_ip` | The IP the message was sent from. |
| (also sent) | `spam_report` | The full SpamAssassin report (when spam check is on). |
| (also sent) | `content-ids` | Identifiers of inline attachments (Content-ID map). |

> **Capitalization matters.** The SPF field is uppercase **`SPF`**; the DKIM field is lowercase **`dkim`**. The app reads `form.get("SPF")` and `form.get("dkim")` — a case mismatch silently yields empty strings.

> **Raw mode replaces these.** If "POST the raw, full MIME message" were ON, the payload would instead carry a single `email` field (full MIME) plus `dkim`, `to`, `from`, `sender_ip`, `spam_report`, `subject`, `spam_score`, `envelope`, `charsets`, `SPF` — and **no** `text`/`html`/`attachmentN`. EmailPOC expects parsed mode (OFF). ([Inbound Parse setup](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook))

> **Size limit.** The total message size (message + all attachments) is **30 MB**. ([Inbound Email](https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/inbound-email))

---

## 9. Test It

### 1. Verify sending identity & DNS

- **Settings > Sender Authentication** shows your Single Sender as **Verified** (4a), or your domain as **Verified** (4b).
- Confirm the inbound MX: `dig MX mail.yourdomain.com` should return `mx.sendgrid.net` at priority `10` and **nothing else**.

### 2. Outbound test

Trigger the app to create a conversation and send an RFQ, or call the Mail Send API directly with curl (note `reply_to` set to the dynamic address):

```bash
curl -s --request POST \
  --url https://api.sendgrid.com/v3/mail/send \
  --header "Authorization: Bearer $SENDGRID_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{
    "personalizations": [{"to": [{"email": "you@example.com"}]}],
    "from": {"email": "noreply@yourdomain.com", "name": "Your Company"},
    "reply_to": {"email": "usr42_conv3fa9c1b2@mail.yourdomain.com"},
    "subject": "RFQ test",
    "content": [{"type": "text/plain", "value": "hello"}]
  }'
```

Success = HTTP **202** with an empty body (SendGrid queued the message). Check **Activity Feed** in the console for delivery.

### 3. Inbound test (simulate the supplier reply)

From your mailbox, **reply** to the RFQ — the `To` becomes the dynamic `Reply-To` `usr42_conv3fa9c1b2@mail.yourdomain.com`. Or send a fresh email straight to that address. SendGrid receives it via the MX and POSTs to your Destination URL.

To simulate SendGrid's POST directly (parsed `multipart/form-data`, matching Section 8 field names) against your running app:

```bash
curl -X POST https://<id>.ngrok-free.app/webhooks/inbound \
  -F 'from=Supplier <supplier@example.com>' \
  -F 'to=usr42_conv3fa9c1b2@mail.yourdomain.com' \
  -F 'subject=Re: RFQ test' \
  -F 'text=Here is our quote.' \
  -F 'html=<p>Here is our quote.</p>' \
  -F 'spam_score=0.1' \
  -F 'SPF=pass' \
  -F 'dkim={@example.com : pass}' \
  -F 'attachments=1' \
  -F 'attachment-info={"attachment1":{"filename":"quote.pdf","type":"application/pdf","content-id":""}}' \
  -F 'attachment1=@/path/to/quote.pdf;type=application/pdf'
```

### 4. What success looks like

- The curl returns **200** from `/webhooks/inbound`.
- The ngrok inspector (`http://127.0.0.1:4040`) shows an incoming **POST → 200**.
- App logs show `Parsed SendGrid inbound: supplier@example.com -> usr42_conv3fa9c1b2@... (1 attachment(s))`, the recipient parsed to `user_id=42` / `conv_id=3fa9c1b2`, and the reply + `quote.pdf` saved.

---

## 10. Troubleshooting

> **DNS propagation.** CNAME/TXT (auth) and MX (inbound) can take minutes up to 24–48h to propagate. Re-click **Verify** in the console as records appear. Confirm with `dig CNAME s1._domainkey.yourdomain.com`, `dig TXT _dmarc.yourdomain.com`, and `dig MX mail.yourdomain.com`.

> **Wrong / missing MX (most common inbound failure).** Confirm exactly one MX on **`INBOUND_DOMAIN`**: value `mx.sendgrid.net`, priority `10`, with **no conflicting MX** (e.g. leftover Google/Microsoft MX). The MX must be on the subdomain, not the apex. `dig MX mail.yourdomain.com` must show `mx.sendgrid.net`.

> **ngrok.** The free tunnel URL **rotates on every restart** — re-paste it into **Settings > Inbound Parse > Destination URL** each time. Use the **https** URL and the path **`/webhooks/inbound`**. The app must listen on **7000** to match `ngrok http 7000`.

> **Parsed vs raw (empty bodies / missing attachments).** If `text`/`html`/`attachmentN` arrive empty, the **"POST the raw, full MIME message"** box is probably **ON** — turn it OFF so SendGrid sends parsed fields. The app reads the parsed fields, not the raw `email` blob.

> **Empty `spam_score` / `SPF` / `dkim`.** `spam_score` (and `spam_report`) are only included when **"Check incoming emails for spam"** is enabled in the Inbound Parse setting. Also mind capitalization: the fields are uppercase **`SPF`** and lowercase **`dkim`** — the parser matches them exactly.

> **Inbound never fires but DNS looks right.** Confirm the **Receiving Domain** in Inbound Parse exactly equals `INBOUND_DOMAIN`, and that you're testing an address on that subdomain (`...@mail.yourdomain.com`, not `...@yourdomain.com`).

> **Bounce loop after authenticating the inbound subdomain.** If you authenticated the *same* subdomain you use for inbound with **Automated Security ON**, its CNAME can collide with the inbound MX and loop. Turn Automated Security OFF for that subdomain, or keep sending-auth and inbound on separate (sub)domains (Section 4b note).

> **Outbound 401/403 on send.** Usually a missing/incorrect `SENDGRID_API_KEY`, or a Restricted key lacking the **Mail Send** scope. Regenerate with Mail Send = Full Access. A 403 on send can also mean the `From` address isn't a verified sender / authenticated domain.

> **Replies not routing to the right conversation.** Confirm the outbound send set **`Reply-To`** (not just `From`) to the dynamic address, so the supplier's reply `To` becomes the dynamic address.

---

## Sources

- Setting up the Inbound Parse webhook (MX, console steps, checkboxes, default & raw parameters): https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/setting-up-the-inbound-parse-webhook
- Inbound Email Parse Webhook (charsets, envelope, 30 MB limit): https://www.twilio.com/docs/sendgrid/for-developers/parsing-email/inbound-email
- How to set up domain authentication (CNAMEs, Automated Security, Link Branding, DMARC): https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication
- Sender Verification (Single Sender Verification): https://www.twilio.com/docs/sendgrid/ui/sending-email/sender-verification
- API Keys (Create API Key, permission levels, Mail Send scope, shown once): https://www.twilio.com/docs/sendgrid/ui/account-and-settings/api-keys
- Inbound Parse (UI overview): https://www.twilio.com/docs/sendgrid/ui/account-and-settings/inbound-parse
