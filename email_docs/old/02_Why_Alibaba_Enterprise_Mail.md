Why We Are Selecting Alibaba Enterprise Mail
---

## 1. The Decision

> **We are selecting Alibaba Enterprise Mail (Alibaba Mail / 阿里云邮箱) as the primary email backbone for IMS.**

It is the **only single vendor** that satisfies all three hard requirements at once:

1. **Reliable delivery into China** (~95% inbox) — its purpose is to reach Chinese suppliers.
2. **Sending under our own domain** `mail.IMS.online` with full SPF/DKIM/DMARC authentication.
3. **Receiving supplier replies** back into our application — natively, via catch-all + IMAP, with no second provider bolted on.

Every other candidate fails at least one of these. Most fail #3.

---

## 2. How Each Alternative Was Eliminated

### 2.1 SendGrid — eliminated on China delivery
SendGrid has the best *mechanics* (true dynamic `From`, native inbound webhook), but it runs on **US infrastructure**. China inbox placement is only **~70%** because the Great Firewall throttles foreign SMTP IPs and Chinese ISPs penalize them. For a China-supplier platform, losing ~3 in 10 emails at the door is unacceptable. It cannot be the backbone — at most a fallback for non-China recipients.

### 2.2 Alibaba DirectMail — eliminated on inbound
DirectMail delivers superbly into China (~95%) and is astonishingly cheap ($0.29/1,000). But it is **outbound-only**: no inbound reception, no MX hosting, no reply webhook. The IMS loop *requires* reading supplier replies, so DirectMail alone breaks the workflow. (It remains an excellent **optional add-on** for high-volume blasts — see §5.)

### 2.3 Tencent Cloud SES — eliminated on inbound
Cheapest sender, best QQ/Foxmail delivery (same parent company). But, like DirectMail, **pure outbound** — no way to receive replies. Same disqualifier.

### 2.4 MXtoChina (Webpower) — eliminated on practicality
Good delivery, but **not self-service** (3–7 day account-manager onboarding), **opaque sales-only pricing**, and only **partial** inbound (reply *notifications*, not full email forwarding). Too slow and too heavy to build on.

### 2.5 Microsoft 365 via 21Vianet — eliminated on fit & cost model
A productivity suite, not an email platform. **Per-mailbox licensing** makes dynamic addressing impossible at scale, and there is **no inbound webhook** — you must poll Microsoft Graph (30–60s latency, constant OAuth token management). Wrong tool, high complexity.

### 2.6 NetEase QiYe — eliminated on developer experience
Near-perfect 163/126 delivery, but **no REST API, no webhook, Chinese-only admin UI**, SMTP-only with a static `From`. Automating it would be painful and dynamic routing is not possible.

---

## 3. Why Alibaba Enterprise Mail Wins — Scorecard

| Requirement | SendGrid | DirectMail | Tencent SES | MXtoChina | M365 | NetEase | **Alibaba Ent. Mail** |
|---|---|---|---|---|---|---|---|
| China delivery ~95% | ❌ ~70% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Send under our domain | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ | ✅ |
| **Receive replies into app** | ✅ | ❌ | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ |
| Single vendor (send+receive) | ❌ | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| Self-service & fast setup | ✅ | ✅ | ✅ | ❌ | ✅ | ⚠️ | ✅ |
| Reasonable cost | ✅ | ✅ | ✅ | ❌ | ⚠️ | ✅ | ✅ |
| English docs | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ❌ | ✅ |
| **All hard requirements met** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **Yes** |

---

## 4. The Core Advantages

1. **One vendor, one domain, one bill.** Sending and receiving live in the same service under `mail.IMS.online`. No fragile hybrid stitching two providers together, no second SPF/DKIM domain to maintain, no split billing.

2. **China-native delivery.** Hosted inside mainland China with direct peering to QQ, 163, and Aliyun — ~95% inbox placement and no Great Firewall penalty. This is exactly where SendGrid fails.

3. **Real inbound, built in.** Catch-all on the subdomain + IMAP means *any* reply to `*@mail.IMS.online` is captured and can be polled (or forwarded to a webhook) by our app — no separate inbound provider required.

4. **Full authentication & compliance.** SPF / DKIM / DMARC on our own domain, plus ICP-ready infrastructure for any future mainland-China hosting needs.

5. **Predictable, low cost.** We need only a few operational mailboxes. A 3-user **Standard** plan (≈ **$135/year, ~$11/month**) covers the entire inbound side.

---

## 5. The Recommended Architecture (and Why It's Robust)

We deliberately **do not** rely on arbitrary per-message `From` addresses (which Alibaba — like most reputable ESPs — restricts to protect deliverability). Instead we use the industry-standard pattern that every professional RFQ/procurement system uses:

```
Fixed verified sender:   rfq@mail.IMS.online
Per-conversation tag:    Reply-To: rfq+<TOKEN>@mail.IMS.online   (catch-all)
                         Subject:  ... [RFQ-<TOKEN>]
                         Header:   X-RFQ-ID: <TOKEN>
Inbound:                 catch-all mailbox  →  IMAP poll / webhook  →  parse <TOKEN>  →  map to conversation
```

**Why this beats "dynamic From":**
- **Deliverability:** one consistent, well-reputed sender address instead of thousands of unknown ones (which trigger spam filters).
- **Resilience:** even if a supplier composes a brand-new email instead of hitting "Reply", the `<TOKEN>` in the subject still maps it to the right conversation.
- **Compliance:** stays within Alibaba's anti-abuse rules — no risk of sender rejection.

### Optional scale-out
For very high outbound volume, **add Alibaba DirectMail** ($0.29/1,000) for the blast/transactional sends while Enterprise Mail keeps handling **all inbound** — same vendor, same domain, no architectural change.

---

## 6. Cost Summary for IMS

| Component | Plan | Cost |
|---|---|---|
| Alibaba Enterprise Mail (inbound + flexible send) | Standard, 3 users | **~$135/year (~$11/mo)** |
| Domain registration/renewal | any registrar | ~$10–20/year |
| Outbound at low volume | included in mailbox / DirectMail PAYG | ~$0–3/mo |
| *Optional* DirectMail for high-volume blasts | 50K package | $13.05 / 6 months |
| *Optional* dedicated IP (deliverability) | — | $128/mo (only if needed) |

**Realistic starting cost: ~$12–15/month, all-in**, scaling cheaply with volume.

---

## 7. Bottom Line

> Alibaba Enterprise Mail is the **only single-vendor solution** that delivers reliably into China **and** receives supplier replies under our own domain. It removes the need for a fragile two-provider hybrid, keeps cost low and predictable, and uses the deliverability-safe **fixed-sender + tracking-token** pattern that scales without hurting sender reputation.

Proceed to **[Report 3 — Implementation Guide](03_Alibaba_Enterprise_Mail_Implementation.md)** for the step-by-step build.
