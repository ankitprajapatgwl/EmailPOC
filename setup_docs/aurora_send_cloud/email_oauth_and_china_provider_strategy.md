# Email Sending & Monitoring Architecture — OAuth Integration + China Provider Strategy

> Source for all China-provider facts/figures: [`email_docs/chinese_mail_providers.md`](email_docs/chinese_mail_providers.md). No details below are assumed or added beyond what that document states.

---

## 1. Bullet Points

### A. Core Email Integration (Gmail / Outlook via OAuth 2.0)

- **Gmail and Microsoft Outlook integration via OAuth 2.0** — users authorize the platform to send emails on their behalf during each session.
- **Per-session authorisation** — no standing email send permission is stored; each session requires explicit user approval at **Gate 3**.
- **Audit trail logging** — all sent emails are logged with **timestamp, recipient, subject, and message ID**.
- **Rate limiting enforced** — a maximum number of emails per hour per user is applied to prevent spam classification.
- **RFQ reply monitoring** — inbound replies are monitored via the same OAuth integration; the **Response Parsing Agent** reads inbound replies only from **approved supplier email threads**.

### B. China-Focused Provider Strategy

- **We are focusing on SendCloud (by Sohu)** as the China email provider, because — per `chinese_mail_providers.md` — it is the only provider in the comparison that offers **all** of the following together:
  - Domain-level authentication (SPF/DKIM/DMARC/MX + tracking CNAME) **without per-sender/mailbox verification**.
  - **Dynamic "From" addresses** via REST API (`/apiv2/mail/send`) or SMTP, once the domain passes SPF+DKIM.
  - **Native inbound parse** — its built-in **Routing/Inbound Parse component** extracts MIME content from supplier replies and forwards it directly to an external webhook, with no need to split MX to a third-party parser.
  - Delivery **optimized for Chinese ISPs** (QQ, 163, Sina) and reported to **bypass the Great Firewall (GFW)** for CN↔CN routing, per the document's cross-border matrix.
  - A direct self-service registration path (no quotation/sales contact needed) — though it is **heavily constrained**: signup strictly requires a **+86 Mainland China mobile number** (Indian +91 numbers are not accepted at signup), and the account starts in a restricted sandbox (10 emails/day, whitelisted recipients only) until corporate identity verification is completed.
- **We are not using other transactional providers such as SendGrid** for Chinese delivery. Per the document, providers outside this China-specific list are only referenced as **inbound-MX-split workarounds** (e.g., "route inbound MX to Mailgun/SendGrid/Postmark") for providers that lack native inbound parse — they are not built for, or optimized around, Mainland China's delivery rules. Routing production mail for Chinese recipients through a non-China-optimized provider like SendGrid carries a higher risk of **delivery failure**, given the document's repeated notes that Mainland-bound mail is subject to:
  - **ICP Filing (备案) with MIIT** requirements for domains sending on domestic lines (flagged as a "Universal compliance requirement" in the document's takeaways).
  - **Keyword/content and anti-spam screening** on Mainland-outbound traffic.
  - The **Great Firewall** itself, which the document states purpose-built providers (MXtoChina, Tencent Cloud SES, SendCloud) are specifically engineered to route around — a capability generic non-China SMTP/API providers are not documented to have.

### C. Planned SendCloud Implementation Workflow

For RFQ emails routed to Chinese suppliers, we will use SendCloud end-to-end as follows:

1. **Subdomain verification** — verify our application's (IMS) own subdomain, e.g. **`mail.ims.com`**, with SendCloud by configuring the required DNS records: **SPF (TXT), DKIM (TXT), DMARC (TXT), MX, and tracking CNAME**. This is **domain-level authentication** — per the source document, once the subdomain is verified, no separate per-mailbox/per-sender verification is required.
2. **Dynamic "From" address generation** — once `mail.ims.com` is verified, we will generate a **dynamic "From" address per user/thread** (e.g. `ankit-000@mail.ims.com`) via SendCloud's REST API (`/apiv2/mail/send`) or SMTP. The document confirms SendCloud supports dynamic "From" addresses at the domain level with **no per-prefix registration**, so any thread-specific address under the verified subdomain can send immediately.
3. **Sending to the Chinese supplier** — the RFQ mail is sent to the Chinese supplier using this dynamically generated, thread-specific "From" address, on the user's behalf.
4. **Reply tracking via webhook** — the supplier's reply is captured through SendCloud's native **Routing/Inbound Parse component**, which extracts the MIME content of the incoming reply and forwards it as a structured payload to our **external webhook URL** — no MX split to a third-party parser (e.g. Mailgun/SendGrid/Postmark) is needed, unlike every other provider in the comparison.
5. **No global/generic providers (e.g., SendGrid)** — reaffirming Section B: we are not using non-China-optimized providers like SendGrid for this flow, because Mainland-bound mail is subject to **ICP filing requirements, content/anti-spam screening, and the Great Firewall** — all of which raise the risk of **email delivery failure** for providers that are not purpose-built for Chinese ISPs.

---

## 2. Provider Comparison Table (Functionality & Cost)

*All values below are taken directly from `chinese_mail_providers.md` — nothing estimated or inferred beyond the source.*

| Provider | What It Is (Functionality) | Indian Developer Access | Dynamic "From" / Inbound Parse | Free Tier | Paid Cost |
|---|---|---|---|---|---|
| **MXtoChina** (MXflow.io) | Shanghai-based **B2B SMTP relay + SMS delivery**; helps bypass the Great Firewall for transactional email (invoices, OTPs, password recovery) into Chinese ISPs. Enforces SPF/DKIM/DMARC. | ⚠️ Yes, but **corporate-only, no self-service** — must apply via request/quotation (info@mxtochina.com / support@mxtochina.com / contact@mxtochina.com) with a business domain and stated use-case. | Dynamic From: ✅ Yes (domain-level auth). Inbound parse: ❌ No — outbound only; must route inbound MX to a third party (Mailgun/SendGrid/Postmark) or self-host. | ❌ None | **Custom quotation only** — no public pricing. Indicative structure: fixed monthly base, baseline ~50,000 emails/month, metered overages; SMS billed separately at CN carrier rates. |
| **Tencent Cloud SES** | Developer-first transactional email **API 3.0 + SMTP**; ~97% in-China delivery via deep ISP routing. | ✅ Yes — **direct self-service**: Indian mobile OTP, international card, Indian govt-ID KYC (2–4 day review). | Dynamic From: ✅ Yes (domain-level, once subdomain passes SPF+DKIM). Inbound parse: ❌ No — outbound-only push service; use `ReplyToAddresses` to an external inbox, or third-party/self-hosted inbound parsing. | ✅ **1,000 free emails** (one-time account allowance) | **Pay-as-you-go:** $0.00028/email beyond free allowance. Optional dedicated IP: $120/month. |
| **NetEase Enterprise Mail** (NetEase QiYe) | Corporate **mailbox/collaboration suite** (like Google Workspace/M365) — not a transactional API. | ⚠️ Yes, **heavily limited** — requires a real-name **+86 China mobile** (for the 16-digit Client Authorization Password) + corporate/passport real-name verification. Officially "not suitable" for overseas/global developer use. | Dynamic From: ❌ No — every sender must be a provisioned mailbox/alias (else SMTP 550). Inbound parse: ❌ No — only traditional inbound rules; workaround via SendGrid/Brevo Inbound Parse or IMAP polling. | ❌ No developer free tier (7-day manual trial only, not scriptable) | **Per-seat/year, 5-seat minimum.** Flagship: ~¥200/user/yr (~$27.60). Deluxe: ~¥260/user/yr (~$35.88). |
| **Alibaba Enterprise Mail** (Aliyun Mail) | **Collaborative corporate mailbox for human employees** (not an API — DirectMail is the API product). Registered via Alibaba Cloud International (Singapore region; India cloud zone closed 15 Jul 2024). | ⚠️ Yes, with restrictions — International Site account, Client Security Password (not a bulk mailer). | Dynamic From: ❌ No — every sender must map to an explicit billable account/alias. Inbound parse: ❌ No — IMAP polling or MX split workaround only. | ❌ No developer free tier (use DirectMail instead) | **Per-user seat subscription** — starts ~$2.87/user/month, 3-seat minimum, 500 GB storage/user; billed annually. |
| **SendCloud (by Sohu)** | Developer-first **transactional + marketing cloud email** (sendcloud.net, unrelated to sendcloud.com); REST API (`/apiv2/mail/send`) + SMTP; optimized for Chinese ISPs (QQ, 163, Sina). | ⚠️ Yes, but constrained — registration **requires a +86 Mainland mobile** (Indian +91 not accepted at signup); starts in sandbox mode until corporate identity verification. | Dynamic From: ✅ Yes (domain-level auth, no per-prefix registration). Inbound parse: ✅ **Yes** — native Routing/Inbound Parse component posts structured MIME data to an external webhook. | ✅ **10 emails/day** (sandbox/trial) | **Base fee + tiered PAYG:** ¥59/month (~$8.14) for 0–10,000 emails; +¥5.6/1,000 (~$0.77) for 10,001–50,000; +¥5.3/1,000 (~$0.73) for 50,001–100,000. No international card billing — requires international bank wire. |
| **Alibaba Cloud DirectMail** | **Outbound-only transactional email engine** on Alibaba Cloud International. | ✅ Yes — fully open with Indian mobile + card; test via `alibabacloud-dm20151123` SDK or SMTP. | Dynamic From: ❌ No — hard limit of 100 pre-registered sender addresses per account. Inbound parse: ❌ No — outbound MNS event webhooks only; needs MX split to a third party or self-hosted parser. | ✅ **2,000 emails/day** | **PAYG:** $0.29 per 1,000 emails after free tier. Prepaid packages: 50k=$13.05, 500k=$121.80, 1M=$230.55. Dedicated IP: $128/month. |
| **Microsoft 365 by 21Vianet** | Sovereign, **China-isolated Exchange Online** instance hosted entirely in Mainland China. | ❌ **No** — requires an onshore Chinese legal entity (WFOE/JV), Chinese Business License, ICP License from MIIT, and a +86 mobile. Cannot register with Indian-only details. | Dynamic From: ❌ No — every sender must be a licensed user/mailbox/alias (else SMTP 550); workaround via Graph API alias provisioning (≤400/mailbox). Inbound parse: ⚠️ No native support — requires Power Automate (21Vianet) or Microsoft Graph Change Notifications. | ❌ No developer free tier (negotiated 7–30 day corporate eval only) | **Annual enterprise subscription, billed in CNY.** O365 E1: ¥66.06/mo (~$9.12); M365 Enterprise Apps: ¥79.27/mo (~$10.94); O365 E3: ¥151.93/mo (~$20.97); M365 E3: ¥192.65/mo (~$26.59). |

---

## 3. Why SendCloud Over the Alternatives (Summary)

| Requirement (from our architecture) | SendCloud | Others (per file) |
|---|---|---|
| Dynamic "From" addresses (needed for per-supplier/per-thread sending) | ✅ Yes | Only MXtoChina and Tencent Cloud SES also support this; all mailbox-style products (NetEase, Alibaba Enterprise Mail, M365-21Vianet) do not |
| Native inbound reply parsing (needed for the Response Parsing Agent) | ✅ Yes — only provider with a built-in inbound webhook | ❌ No other provider in the document has native inbound parse; all require an MX-split workaround to a third party or self-hosted listener |
| Optimized delivery / GFW bypass for Chinese recipients | ✅ Yes (per cross-border matrix) | MXtoChina also purpose-built for this, but is quotation-only with no public pricing |
| Reason to avoid SendGrid-style generic providers | Not purpose-built for Mainland delivery; document lists such providers only as inbound-MX-split fallbacks, not as primary China-delivery options — combined with ICP filing rules, content screening, and the Great Firewall, this raises the risk of delivery failure | — |

---

*All figures, capabilities, and constraints in Sections 2 and 3 are quoted or directly derived from `email_docs/chinese_mail_providers.md`. Section 1A (OAuth/Gmail/Outlook architecture) reflects points provided directly for this document.*
