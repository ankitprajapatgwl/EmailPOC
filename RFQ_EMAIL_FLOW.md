# Sending Emails to Suppliers on Behalf of the User — Flow & Approach

This document explains, in simple words, how our system sends emails to suppliers **on behalf of a user**, and how we track supplier replies back to the correct user and product. It also explains why we moved away from SendGrid for China, what we built as a Proof of Concept (POC), other providers we could not implement due to registration blockers, a known limitation with the Chinese providers, and a final comparison table of all the email providers we researched.

---

## 1. What Problem Are We Solving?

When a user searches for a product, our system needs to email multiple suppliers on that user's behalf, asking for quotes (RFQ). We need to:

1. Send the email so it looks like it's coming from the user (or our platform, on their behalf), without needing to verify every single sender email address one by one.
2. Know exactly **which supplier replied**, and **for which product/search**, when the response comes back.
3. Catch that reply automatically in our backend, without a human having to check an inbox.

To do this, we designed the flow below.

---

## 2. Our Flow — Step by Step

### Step 1: Register our domain with the email provider

First, we register our own sending domain (example: `https://ims.com`, or a subdomain like `mail.ims.com`) with the email provider. This is a one-time setup where we add some DNS records (SPF, DKIM, MX, etc.) to prove we own the domain.

**Why this matters:** Once the *domain* is verified, the provider allows us to send email from **any address under that domain** dynamically — we do not need to verify each sender email address separately. This is what makes dynamic, on-the-fly sending possible.

### Step 2: Give each user one permanent sending address, and each conversation one hidden tracking address

Two different addresses are involved on the outbound side, and they do two different jobs:

1. **Permanent sending address — one per user, assigned once at registration.** When a user signs up, we assign them a stable address under our domain (e.g. `james.doe@mail.ims.com`, derived from the local part of their personal email). This is the address suppliers actually **see** in the `From` field on every RFQ we send on that user's behalf, no matter which supplier or product it's about. We use a real-looking, permanent address here — instead of the old approach of putting a fresh disposable-looking address (`james-1111@mail.ims.com`) in `From` — because a random-looking `From` address reads as spam/disposable to suppliers and hurts deliverability and trust.
2. **Dynamic conversation address — one per supplier, per product search, generated on the fly.** This is unchanged from before: for every product a user searches for, we still generate a **unique, one-time address** per supplier (e.g. `james-1111@mail.ims.com`), with a unique ID baked in that's linked in our database to the user, the product search, and the supplier. The only difference is *where* it's placed — it now goes in the `Reply-To` header instead of `From`, so it's invisible to the supplier unless they inspect headers, but it's still the address their mail client will actually send the reply to.

**Example:** If a user searches for "Bluetooth speaker," every outgoing email shows the same `From`, but carries a different hidden `Reply-To` per supplier:

| Supplier | Visible `From` (permanent, per-user) | Hidden `Reply-To` (dynamic, per-conversation) |
|---|---|---|
| John | james.doe@mail.ims.com | james-0000@mail.ims.com |
| Sam  | james.doe@mail.ims.com | james-1111@mail.ims.com |
| Elon | james.doe@mail.ims.com | james-2222@mail.ims.com |

**Why this matters:** This split gives us both properties at once. Suppliers see one trustworthy, human-looking address per user, which keeps deliverability high, while our backend still gets a distinct `Reply-To` address per conversation so replies can be routed automatically. As a further safety net, every RFQ body also carries a plain-text reference footer (`Reference: CONV-3FA9C1B2 | USR-42`) — a second, redundant place the conversation ID lives, used as a fallback in Step 3 below.

### Step 3: Catch supplier replies via Inbound Parse Webhook

On the email provider's dashboard, we configure an **Inbound Parse Webhook URL**. This tells the provider: "Whenever mail arrives at any address under our domain, don't just deliver it to an inbox — send its contents as an HTTP request to this URL instead."

When mail comes in, our backend tries to resolve it to the right conversation using three fallback tiers, each covering a gap the previous one can't:

1. **Dynamic `Reply-To` address (the normal case).** The `To` address on the inbound mail is `james-1111@mail.ims.com`; we decode the embedded ID directly and immediately know this is **Sam**, about the **Bluetooth speaker** request, for **this specific user**.
2. **`CONV-` reference footer in the quoted body.** Some mail clients mangle or drop the dynamic address when a supplier forwards instead of replying (autocomplete or an address-book entry can strip the `-{conv_id}` suffix). When that happens, we fall back to searching the quoted body for the `Reference: CONV-...` footer from Step 2, which the supplier's client normally preserves even when the address itself gets mangled.
3. **Reverse lookup by the user's permanent sending address.** If a supplier ignores Reply/Forward entirely and composes a brand-new email, there is no dynamic address and no quoted footer anywhere in the message (see Section 5 below). But the message is still addressed to the user's permanent sending address from Step 2, and that address belongs to exactly one user. We look up the owning user from it, then file the email under their most recent existing conversation with that supplier — or open a new conversation if that supplier has never contacted this user before.

Only if all three tiers fail is the email logged as unmatched for manual review. This completes the loop: **User searches → We email suppliers → Supplier replies (or, now, sometimes even a fresh email) → We catch and route it back to the right user/conversation automatically.**

---

## 3. Why We Moved Away From SendGrid for China

Our first POC for this entire flow was built using **SendGrid**, and it worked well — domain-level sending, dynamic "From" addresses, and Inbound Parse Webhooks all worked exactly as needed.

However, when it came to sending emails to **suppliers based in China**, we ran into a problem: **Chinese government regulations** restrict/limit how foreign (non-Chinese) email and cloud providers can deliver mail to Mainland China. Mail routed through a non-China-based provider like SendGrid faces a much higher risk of being blocked, filtered, or simply not delivered to Chinese ISPs (QQ, 163/NetEase, etc.), due to rules like mandatory ICP filing, strict content/anti-spam screening, and the Great Firewall.

Because of this, **SendGrid could not be reliably used for our China region**, and we had to specifically look for and adopt Chinese (or China-optimized) email providers instead.

---

## 4. What We Built in the POC

For the China region, we implemented and tested **two Chinese email providers**:

- **EngageLab**
- **AuroraSendCloud** (the global product line of the Chinese provider SendCloud, by Sohu)

Both providers support the full flow described above:
- Domain-level verification (no need to verify every sender individually)
- Dynamic addresses generated on the fly, per supplier/conversation, usable as either `From` or `Reply-To`
- An Inbound Route / Webhook feature to catch supplier replies and push them to our backend

---

## 5. A Known Limitation: New Email Threads Are Not Tracked (Partially Mitigated)

There is one important limitation we discovered while testing EngageLab and AuroraSendCloud — this is a restriction enforced by the **provider itself**, before a message ever reaches our webhook, and it's separate from the backend matching described in Step 3 above.

- ✅ **If the supplier clicks "Reply" or "Forward"** on our email, everything works perfectly. We get notified, and we can track the response.
- ❌ **If the supplier instead starts a brand-new email** (types our address fresh, instead of replying), the provider may **never deliver it to our webhook at all**.

**Why this happens:** When a supplier hits Reply/Forward, their email client automatically carries forward hidden tracking information in the email headers (called `In-Reply-To` and `References`, plus the `Message-ID`). Both EngageLab and AuroraSendCloud rely on this hidden metadata to match an incoming email back to the original outgoing message. If a supplier starts a brand-new email, none of this metadata exists — so these providers treat it as an unrelated, untrackable message and simply drop it, regardless of which address it was sent to. In short, EngageLab and AuroraSendCloud behave like **closed-loop transaction routers**: they only recognize mail that is clearly a reply to something we already sent.

**What we've since added on our side:** our backend can now bind a completely headerless, brand-new email — no dynamic address, no `CONV-` footer — to the right user and conversation, by reverse-looking-up the user's permanent sending address (Step 3, tier 3 above). This closes the *attribution* half of the problem: if a new-thread email does reach our webhook, we no longer discard it as unmatched — we can tell exactly which user it belongs to, and file it under the right conversation with that supplier (or open a new one).

**What this does *not* fix:** for EngageLab and AuroraSendCloud specifically, the provider-level restriction described above still applies — a brand-new email with no `In-Reply-To`/`References` headers can be dropped by their Inbound Route before it ever reaches our webhook, no matter what address it's sent to. Our new fallback can't act on a message we never received. So this improvement mainly helps (a) providers whose inbound route forwards all mail regardless of headers (e.g. SendGrid), and (b) Reply/Forward messages whose dynamic address got mangled or stripped in transit, which tier 2 already handled and tier 3 backs up.

**How SendGrid is different:** SendGrid does not have this limitation. SendGrid's Inbound Parse works by making SendGrid the actual mail server (MX) for our domain — so it captures **any** email sent to our domain, whether it's a reply or a brand-new message, and sends it to our webhook regardless of whether reply-tracking headers are present. This is because SendGrid is architected as an open MX-level mail catcher, not a transaction-matching system.

So, for Chinese suppliers, a supplier who ignores Reply/Forward and composes a fresh email is still invisible to us today — our reply tracking reliably works for Reply/Forward, and our backend is now ready to attribute a fresh-thread email correctly the moment the provider side of this gap closes.

---

## 6. Other Providers We Could Implement — But Registration Blockers Stopped Us

Besides EngageLab and AuroraSendCloud, there are **3 more Chinese providers** we could potentially implement in this POC: **Alibaba Cloud DirectMail**, **SUBMAIL**, and **Baidu Cloud SES**. However, each of these has a registration problem that blocks us today:

| Provider | Can We Register With an Indian Mobile Number? | Blocker |
|---|---|---|
| **Alibaba Cloud DirectMail** | ❌ No | Registration itself does not go through with an Indian mobile number — we get stuck before we can even create a usable account. |
| **Baidu Cloud SES** | ❌ No | Same issue as Alibaba Cloud DirectMail — registration with an Indian mobile number does not work. |
| **SUBMAIL** | ✅ Yes | Registration itself works with an Indian mobile number, but before we're allowed to actually use the service, the platform requires us to submit **Business Registration Documents** for verification. |

Because of these blockers, none of these three could be taken further in this POC — two are stuck at the registration step itself, and the third needs business verification documents to be submitted and approved before it can be used.

---

## 7. Provider Comparison Table

Below is a comparison of all the email providers we researched, checked against our core requirements: **(a)** domain-level verification without per-sender verification, **(b)** dynamic "From" address support, and **(c)** Inbound Parse webhook support for catching replies. Costing is included for each.

| Provider | Dynamic "From" Addresses | Inbound Reply Webhook | Free Tier | Paid Cost | Meets Our Requirement? |
|---|---|---|---|---|---|
| **SendGrid** | ✅ Yes | ✅ Yes — catches replies **and** brand-new emails | Limited free tier | Standard SendGrid plans | ✅ Works fully, but **cannot be used for China** due to Chinese regulations |
| **EngageLab** | ✅ Yes (domain-level, no per-prefix registration) | ⚠️ Partial — only catches Reply/Forward, not new threads | ✅ 50 emails/day free | $29.90/month for 10,000 emails; $127.00/month for 50,000 emails | ✅ Used in our POC for China |
| **AuroraSendCloud** (SendCloud global) | ✅ Yes (domain-level, no per-prefix registration) | ⚠️ Partial — only catches Reply/Forward, not new threads; attachments on replies are not relayed | ❌ No confirmed free tier | Prepaid credit packs, valid 1 year: 10,000 emails = $29.90; 30,000 = $85.00; 50,000 = $130.00; 100,000 = $250.00; 150,000 = $360.00; 300,000 = $670.00; 500,000 = $1,050.00 | ✅ Used in our POC for China |
| **Tencent Cloud SES** | ✅ Yes (domain-level) | ❌ No — outbound-only; replies must go to an external inbox via `ReplyToAddresses`, or need a third-party inbound parser | ✅ 1,000 free emails (one-time) | $0.00028/email pay-as-you-go; optional dedicated IP $120/month | ❌ No native inbound tracking — rejected |
| **MXtoChina** (MXflow.io) | ✅ Yes (domain-level) | ❌ No — outbound only; needs a third-party inbound parser or self-hosting | ❌ None | Custom quotation only (no public pricing); indicative baseline ~50,000 emails/month | ❌ No inbound tracking, and no self-service signup — rejected |
| **NetEase Enterprise Mail** | ❌ No — every sender must be a pre-created mailbox | ❌ No — only basic inbound rules, no webhook | ❌ No developer free tier | ~$27.60–$35.88/user/year, 5-seat minimum | ❌ Rejected — no dynamic sending, no inbound webhook |
| **Alibaba Enterprise Mail** | ❌ No — every sender must be a pre-registered account/alias | ❌ No — no inbound webhook | ❌ No developer free tier | Starts ~$2.87/user/month, 3-seat minimum | ❌ Rejected — no dynamic sending, no inbound webhook |
| **Alibaba Cloud DirectMail** | ❌ No — hard limit of 100 pre-registered senders | ❌ No — outbound-only event webhooks, no inbound parsing | ✅ 2,000 emails/day free | $0.29 per 1,000 emails after free tier | ❌ Rejected — no dynamic sending, no inbound webhook, and **registration itself fails with an Indian mobile number** (see Section 6) |
| **SUBMAIL** | ⚠️ Not evaluated | ⚠️ Not evaluated | ⚠️ Not evaluated | ⚠️ Not evaluated | ❌ Rejected — registration works, but the platform requires **Business Registration Documents to be verified** before the service can be used (see Section 6) |
| **Baidu Cloud SES** | ⚠️ Not evaluated | ⚠️ Not evaluated | ⚠️ Not evaluated | ⚠️ Not evaluated | ❌ Rejected — **registration itself fails with an Indian mobile number** (see Section 6) |
| **Microsoft 365 (21Vianet)** | ❌ No — every sender must be a licensed mailbox/alias | ❌ No native inbound parse (needs Power Automate workaround) | ❌ No developer free tier | ¥66–¥193/user/month (billed annually in CNY) | ❌ Rejected — no dynamic sending, requires a Chinese legal entity to even sign up |

**Summary:** Only **EngageLab** and **AuroraSendCloud** satisfy both of our core requirements (dynamic "From" addresses + inbound reply webhook) while also being usable for Chinese suppliers — which is why both were implemented in this POC, with the one known limitation on new-thread tracking noted in Section 5 above. **Alibaba Cloud DirectMail**, **SUBMAIL**, and **Baidu Cloud SES** remain unimplemented purely due to the registration blockers noted in Section 6 — not because of any functionality gap that was tested and found lacking.
