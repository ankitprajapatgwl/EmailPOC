# Report 3 — Alibaba Enterprise Mail Implementation Guide

> **Document:** 3 of 3 | **Date:** June 30, 2026
> **Platform:** JobSetU | **Domain:** `mail.jobsetu.online`
> **Prepared for:** Ankit @ Galaxy Web Links
> **Companion reports:** [01 — Provider Analysis](01_China_Email_Provider_Analysis.md) · [02 — Why Alibaba Enterprise Mail](02_Why_Alibaba_Enterprise_Mail.md)

---

## 1. Target Architecture

```
                         JobSetU App
                              │
            ┌─────────────────┴──────────────────┐
            │ (1) SEND                            │ (4) INGEST
            ▼                                     ▲
   SMTP: smtp.qiye.aliyun.com               IMAP: imap.qiye.aliyun.com
   FROM:    rfq@mail.jobsetu.online          (catch-all mailbox)
   Reply-To: rfq+<TOKEN>@mail.jobsetu.online        │
   Subject:  ... [RFQ-<TOKEN>]                       │
   X-RFQ-ID: <TOKEN>                                 │
            │                                        │
            ▼                                        │
      China Supplier  ──── (3) clicks Reply ────────►┘
        (2) receives           reply goes to
            inquiry            rfq+<TOKEN>@mail.jobsetu.online
                               (caught by catch-all)
```

**Key design choice (from Report 2):** a **fixed verified sender** + **per-conversation tracking token** in `Reply-To`/subject/header, with a **catch-all** mailbox ingested over **IMAP**. This is deliverability-safe and survives suppliers who start a fresh email instead of hitting Reply.

---

## 2. Prerequisites

| Item | Detail |
|---|---|
| Alibaba Cloud account | International site (`alibabacloud.com`) — free to create |
| Domain | `jobsetu.online` (already owned). We will use subdomain `mail.jobsetu.online` |
| Alibaba Enterprise Mail plan | **Standard, 3 users** (~$135/yr) — sufficient for `rfq@`, `noreply@`, catch-all |
| DNS access | To add MX, SPF, DKIM, DMARC, and ownership-verification records |
| App runtime | Node.js (matches existing JobSetU POC); `nodemailer` (SMTP) + `imapflow` / `node-imap` (IMAP) |

> **VPN:** Not required. Alibaba Cloud public endpoints are reachable from India/globally. A VPN is optional only if you hit latency issues.

---

## 3. Step-by-Step Setup

### Step 1 — Activate Enterprise Mail & add the domain
1. Alibaba Cloud Console → **Enterprise Mail (企业邮箱)** → purchase **Standard, 3 users**.
2. Add domain `mail.jobsetu.online` (or `jobsetu.online` and use the `mail.` subdomain for mailboxes).
3. The console issues DNS records to prove ownership and route mail.

### Step 2 — Configure DNS
Add these at your DNS provider (values shown by the Alibaba console — examples below):

| Type | Host | Value | Purpose |
|---|---|---|---|
| MX | `mail` | `mxhichina.com` (priority 5/10 as given) | Route inbound to Alibaba |
| TXT (SPF) | `mail` | `v=spf1 include:spf.qiye.aliyun.com -all` | Authorize senders |
| TXT (DKIM) | `<selector>._domainkey.mail` | (key from console) | Sign outbound |
| TXT (DMARC) | `_dmarc.mail` | `v=DMARC1; p=quarantine; rua=mailto:dmarc@jobsetu.online` | Policy + reports |
| TXT (verify) | `mail` | (ownership token from console) | Domain verification |

Wait for propagation, then click **Verify** in the console until all records show green.

### Step 3 — Create mailboxes & enable catch-all
1. Create operational mailboxes: `rfq@mail.jobsetu.online`, `noreply@mail.jobsetu.online`.
2. Create a **catch-all** mailbox, e.g. `catchall@mail.jobsetu.online`, and in **Domain Settings → Catch-all / 默认邮箱**, route all unmatched addresses (`*@mail.jobsetu.online`) to it. This is what captures every `rfq+<TOKEN>@...` reply.
3. Enable **SMTP/IMAP access** for these mailboxes (Account settings → enable client protocols; you may need to set a client/authorization password).

### Step 4 — Record connection settings

| Protocol | Server | Port | Security |
|---|---|---|---|
| SMTP (send) | `smtp.qiye.aliyun.com` | 465 | SSL/TLS |
| IMAP (receive) | `imap.qiye.aliyun.com` | 993 | SSL/TLS |

Store credentials in environment variables (never in code):

```bash
# .env  — do NOT commit
ALIYUN_SMTP_HOST=smtp.qiye.aliyun.com
ALIYUN_SMTP_PORT=465
ALIYUN_SMTP_USER=rfq@mail.jobsetu.online
ALIYUN_SMTP_PASS=__client_auth_password__

ALIYUN_IMAP_HOST=imap.qiye.aliyun.com
ALIYUN_IMAP_PORT=993
ALIYUN_IMAP_USER=catchall@mail.jobsetu.online
ALIYUN_IMAP_PASS=__client_auth_password__

MAIL_DOMAIN=mail.jobsetu.online
SENDER_ADDRESS=rfq@mail.jobsetu.online
```

---

## 4. Sending an RFQ (outbound)

```javascript
// mailer.js
const nodemailer = require('nodemailer');
const crypto = require('crypto');

const transporter = nodemailer.createTransport({
  host: process.env.ALIYUN_SMTP_HOST,
  port: Number(process.env.ALIYUN_SMTP_PORT),
  secure: true, // SSL on 465
  auth: {
    user: process.env.ALIYUN_SMTP_USER,
    pass: process.env.ALIYUN_SMTP_PASS,
  },
});

// One opaque token per user↔supplier conversation
function makeToken() {
  return crypto.randomBytes(6).toString('hex'); // e.g. "a3f9c1d2e4b5"
}

async function sendRFQ({ user, supplier, subject, html }) {
  const token = makeToken();

  // Persist the mapping BEFORE sending so inbound can always resolve it
  await db.conversations.insert({
    token,
    userId: user.id,
    supplierId: supplier.id,
    sender: process.env.SENDER_ADDRESS,
    createdAt: new Date(),
  });

  const replyTo = `rfq+${token}@${process.env.MAIL_DOMAIN}`;

  await transporter.sendMail({
    from: `"JobSetU RFQ" <${process.env.SENDER_ADDRESS}>`, // fixed, verified sender
    to: supplier.email,
    replyTo,                                                // per-conversation routing
    subject: `${subject} [RFQ-${token}]`,                   // token survives "new email" replies
    html,
    headers: { 'X-RFQ-ID': token },                         // machine-readable fallback
  });

  return token;
}

module.exports = { sendRFQ };
```

**Why the token appears in three places** — `Reply-To`, subject, and a custom header — is redundancy: whichever one survives the supplier's mail client lets us map the reply back.

---

## 5. Receiving replies (inbound via IMAP)

A worker polls the catch-all mailbox, extracts the token, and stores the reply.

```javascript
// inbound-worker.js
const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');

const client = new ImapFlow({
  host: process.env.ALIYUN_IMAP_HOST,
  port: Number(process.env.ALIYUN_IMAP_PORT),
  secure: true,
  auth: {
    user: process.env.ALIYUN_IMAP_USER,
    pass: process.env.ALIYUN_IMAP_PASS,
  },
});

// Pull the token from To/Reply-To (rfq+TOKEN@...), subject [RFQ-TOKEN], or X-RFQ-ID
function extractToken({ to, subject, headers }) {
  const plus = (to || '').match(/rfq\+([a-f0-9]+)@/i);
  if (plus) return plus[1];
  const subj = (subject || '').match(/\[RFQ-([a-f0-9]+)\]/i);
  if (subj) return subj[1];
  const hdr = headers?.get?.('x-rfq-id');
  if (hdr) return hdr;
  return null;
}

async function pollInbound() {
  await client.connect();
  const lock = await client.getMailboxLock('INBOX');
  try {
    // Only unseen messages
    for await (const msg of client.fetch({ seen: false }, { source: true, envelope: true })) {
      const parsed = await simpleParser(msg.source);

      const token = extractToken({
        to: parsed.to?.text,
        subject: parsed.subject,
        headers: parsed.headers,
      });

      const conversation = token ? await db.conversations.findByToken(token) : null;

      if (!conversation) {
        // Fallback: park in a manual-review queue instead of dropping
        await db.unmatchedReplies.insert({ raw: parsed.subject, from: parsed.from?.text });
      } else {
        await db.replies.insert({
          conversationId: conversation.id,
          from: parsed.from?.text,
          subject: parsed.subject,
          body: parsed.text || parsed.html,
          attachments: (parsed.attachments || []).map(a => ({
            filename: a.filename, size: a.size, contentType: a.contentType,
          })),
          receivedAt: new Date(),
        });
        await notifyUser(conversation.userId, 'New reply from supplier');
      }

      await client.messageFlags(msg.uid, ['\\Seen'], { uid: true }); // mark processed
    }
  } finally {
    lock.release();
    await client.logout();
  }
}

// Run on an interval (e.g. every 30–60s) or via a cron worker
setInterval(() => pollInbound().catch(console.error), 45_000);
```

> **Optional webhook style:** if you prefer push over poll, run this worker and have it `POST` each parsed reply to your existing `/webhooks/inbound` endpoint instead of writing to the DB directly — keeping the rest of the app unchanged.

---

## 6. Data Model (minimal)

```
conversations
  token        TEXT  UNIQUE  -- maps reply ➜ conversation
  user_id      FK
  supplier_id  FK
  sender       TEXT
  created_at   TIMESTAMP

replies
  conversation_id  FK
  from             TEXT
  subject          TEXT
  body             TEXT
  attachments      JSON
  received_at      TIMESTAMP

unmatched_replies   -- manual review queue for tokenless replies
  raw   TEXT
  from  TEXT
```

---

## 7. Testing Plan (local machine)

1. **DNS check:** `dig MX mail.jobsetu.online`, `dig TXT mail.jobsetu.online` — confirm MX + SPF/DKIM/DMARC resolve.
2. **Outbound:** call `sendRFQ()` to a test Chinese inbox (163/QQ) — confirm it lands in **inbox**, not spam, and `Reply-To` shows `rfq+<token>@...`.
3. **Inbound:** reply from that test inbox → run `pollInbound()` → confirm a `replies` row links to the right `conversation.token`.
4. **Resilience:** send a **brand-new** email (not a reply) with `[RFQ-<token>]` only in the subject → confirm it still maps.
5. **Fallback:** send a reply with **no token** → confirm it lands in `unmatched_replies`, not lost.
6. **Attachments:** reply with a PDF/image → confirm metadata is captured.

---

## 8. Production Hardening

- **Deliverability:** keep the `From` display name consistent; warm up volume gradually; consider a **dedicated IP** ($128/mo) only if reputation issues appear.
- **Secrets:** all credentials in env/secret manager; rotate the IMAP/SMTP client passwords.
- **Idempotency:** dedupe inbound by `Message-ID` so a re-polled message is never stored twice.
- **Monitoring:** alert if the inbound worker stalls (no successful poll in N minutes) or SMTP send failures spike.
- **Compliance:** include unsubscribe/identification footer per anti-spam norms; for any mainland-China data hosting, confirm PIPL/ICP requirements with legal.
- **Scale-out:** if outbound volume grows, route blasts through **Alibaba DirectMail** ($0.29/1,000) while Enterprise Mail keeps handling inbound — no architecture change.

---

## 9. Implementation Checklist

- [ ] Create Alibaba Cloud account (international site)
- [ ] Purchase Enterprise Mail **Standard (3 users)**
- [ ] Add & verify domain `mail.jobsetu.online`
- [ ] Configure MX, SPF, DKIM, DMARC DNS records
- [ ] Create `rfq@`, `noreply@`, `catchall@` mailboxes
- [ ] Enable **catch-all** routing to `catchall@`
- [ ] Enable SMTP/IMAP client access + set auth passwords
- [ ] Wire `sendRFQ()` (nodemailer) into the app
- [ ] Wire `pollInbound()` (imapflow) worker
- [ ] Add `conversations` / `replies` / `unmatched_replies` tables
- [ ] Run the 6-step test plan
- [ ] Add monitoring + secret rotation before go-live

---

*Sources: [Alibaba Mail docs](https://www.alibabacloud.com/help/en/alibaba-mail/) · [Alibaba Mail pricing](https://www.alibabacloud.com/en/product/alibaba-mail/pricing) · [DirectMail pricing](https://www.alibabacloud.com/en/product/directmail/pricing). Server hostnames/DNS values shown are typical Alibaba Enterprise Mail defaults — always use the exact values your console displays.*
