# Chinese Email Providers — Comparison for a Python Send & Monitoring System

> **Scope & sources:** Every provider was evaluated against the same set of questions for an **Indian developer** using **Indian details** and an **Indian GoDaddy domain**, building a **Python** send-and-monitoring system.
>
> **Providers covered:**
> 1. MXtoChina (MXflow.io — Webpower China)
> 2. Tencent Cloud SES (Simple Email Service)
> 3. NetEase Enterprise Mail (网易企业邮箱 / NetEase QiYe)
> 4. Alibaba Enterprise Mail (阿里企业邮箱 / Aliyun Mail)
> 5. SendCloud (by Sohu)
> 6. Alibaba Cloud DirectMail
> 7. Microsoft 365 operated by 21Vianet
>
> **Note:** **NetEase Enterprise Mail** and **NetEase QiYe** are the *same product* — "NetEase QiYe" (网易企业邮箱) is simply the native Chinese brand name of NetEase Enterprise Mail. They are covered as a single provider here.

---

## 1. Short Description of Each Provider

- **MXtoChina (MXflow.io):** A specialized, **Shanghai-based B2B SMTP relay *and* SMS delivery** service operated by Webpower China (offices in Netherlands, Hong Kong, Shanghai). Purpose-built to help international businesses/developers bypass the "Great Firewall" and reliably deliver transactional email (invoices, password recoveries, OTPs) and marketing SMS into mainland China's local ISPs. Enforces SPF/DKIM/DMARC compliance. **Open to verified corporate/professional identities (including Indian) — but via request/quotation only; no instant self-service signup.**

- **Tencent Cloud SES:** A developer-first transactional cloud email API/SMTP service on Tencent Cloud International. Domain-level authentication, dynamic senders, outbound event webhooks, and deep routing into Chinese ISPs (~97% in-China delivery). **Open to Indian developers.**

- **NetEase Enterprise Mail (网易企业邮箱 / NetEase QiYe):** A corporate mailbox/collaboration suite (like Google Workspace / M365), not a transactional API. Strict per-mailbox sender authorization. **Registrable by an Indian developer, but with heavy infrastructure limitations** — mandates a real-name-authenticated **Chinese (+86) mobile number** to generate the 16-digit Client Authorization Password, plus corporate- or passport-based real-name verification to lift external IP restrictions (`ERR.LOGIN.IPDENY`). Officially stated to be optimized for domestic operations and *not* suitable for overseas/global developer use.

- **Alibaba Enterprise Mail (Aliyun Mail):** A corporate workforce mailbox suite managed via Alibaba Cloud International. Strict per-mailbox sender verification, but registrable with Indian details (with programmatic restrictions). Has a free edition.

- **SendCloud (by Sohu):** A Chinese developer-first transactional + marketing cloud email platform (spun off from Sohu). Domain-level auth, dynamic senders, outbound webhooks, optimized for delivery into Chinese ISPs. **Open to Indian developers with constraints; has a free daily quota.**

- **Alibaba Cloud DirectMail:** An outbound-only transactional email engine on Alibaba Cloud International. Registrable with Indian details, includes a lifetime free quota, but requires each sender address to be pre-registered (no wildcard/dynamic senders).

- **Microsoft 365 operated by 21Vianet:** The sovereign, China-isolated instance of Microsoft 365 (Exchange Online) hosted entirely inside Mainland China. Not an open SMTP relay, but uniquely offers inbound parsing via Microsoft Graph Change Notifications. **Requires Chinese business credentials to register.**

---

## 2. Functionality Comparison

### 2a. Core Capabilities & Developer Access

This table answers: **(Q1)** Can an Indian developer register & test with Python? · Domain verification without per-sender verification · Custom dynamic "From" addresses · **(Q3)** Inbound Parse webhook support.

| Provider | Service Type | Indian Dev Register + Python Test? (Q1) | Domain Verification w/o Sender Verification | Custom Dynamic "From" Addresses | Inbound Parse via Webhook (Q3) |
|---|---|---|---|---|---|
| **MXtoChina** | B2B SMTP relay + SMS delivery | ⚠️ YES (corporate-only, no self-service) — Indian devs *can* register, but only as a verified corporate/professional identity (not casual individuals). Requires a business email on your own domain, verified domain control, and a stated compliance use-case. Onboard via request/quotation to info@mxtochina.com; 2FA enforced. | ✅ YES — SPF/DKIM/DMARC domain-level; no per-inbox verification | ✅ YES — dynamic From accepted & signed under verified domain | ❌ NO — outbound tracking only; workaround: route inbound MX to Mailgun/SendGrid/Postmark or self-host aiosmtpd/Haraka |
| **Tencent Cloud SES** | Developer transactional API/SMTP | ✅ YES — **direct self-service signup (no quotation/sales contact)**; Indian details + Indian mobile OTP (+91) + international payment card + KYC govt-ID (2–4 day review); email/Google SSO; instant Python test via API Explorer or `tencentcloud-sdk-python` | ✅ YES — domain-level auth via **SPF + DKIM** (Tencent advises a third-level subdomain, e.g. `mail.ims.com`, over the root domain); once verified, any prefix under it sends without per-address verification | ✅ YES — dynamic From via API 3.0 (SendEmail) or SMTP | ❌ NO — outbound-only push service; workaround: use `ReplyToAddresses` to an external inbox, or SendGrid/Mailgun inbound parse / self-host aiosmtpd/Haraka |
| **NetEase Enterprise Mail** (NetEase QiYe) | Corporate mailbox suite | ⚠️ YES (heavy limitations) — requires a real-name-authenticated **+86 China mobile** (to issue the 16-digit Client Authorization Password) + corporate- or **passport**-based real-name verification to lift IP restrictions (`ERR.LOGIN.IPDENY`). Officially not suitable for overseas/global dev use. | ❌ NO — every sender must be a provisioned mailbox/group/alias (else SMTP 550) | ❌ NO — blocked; NetEase directs high-volume dynamic pipelines to a transactional relay (SendGrid / Tencent SES / Aliyun DirectMail) | ❌ NO — traditional inbound rules only; workaround: route MX to SendGrid/Brevo Inbound Parse, or IMAP IDLE polling |
| **Alibaba Enterprise Mail** | Corporate mailbox suite | ⚠️ YES (with restrictions) — Alibaba Cloud Intl account w/ Indian details; uses Client Security Password, not an open bulk mailer | ❌ NO — sender prefix must be pre-registered user/group/alias | ❌ NO — sender mismatch block; workaround: API alias provisioning, or pivot to Tencent SES / SendCloud | ❌ NO — admin events only; workaround: IMAP polling or MX split to SendGrid/Postmark/Mailgun |
| **SendCloud (by Sohu)** | Developer transactional/marketing cloud | ⚠️ YES (with constraints) — register w/ Indian mobile, but starts in Sandbox mode (sending only to whitelisted test recipients until vetted) | ✅ YES — domain-level (SPF/DKIM/MX); no per-prefix registration | ✅ YES — dynamic From via HTTP REST API (/apiv2/mail/send) or SMTP | ❌ NO — outbound events only; workaround: MX to SendGrid/Postmark/Mailgun or self-host aiosmtpd/Haraka |
| **Alibaba Cloud DirectMail** | Outbound-only transactional engine | ✅ YES — Alibaba Cloud Intl w/ Indian details; `alibabacloud-dm20151123` SDK or SMTP | ❌ NO — each exact sender prefix must be pre-registered (else InvalidSenderAddress) | ❌ NO — workaround: pre-provisioned sender pool via OpenAPI SDK (quota-limited), or pivot to Tencent SES / SendCloud | ❌ NO — uses MNS event webhooks for outbound only; workaround: MX split to third-party parser or self-host aiosmtpd/Haraka |
| **M365 by 21Vianet** | Sovereign Exchange Online (China) | ❌ NO — requires Mainland China business license + +86 mobile; cannot register on microsoftonline.cn with Indian details | ❌ NO — Exchange Online not an open relay; sender must be licensed user/shared mailbox/alias (else SMTP 550) | ❌ NO — workaround: Graph API alias provisioning (≤400 aliases/mailbox) via chinacloudapi.cn, or bypass to Tencent SES / Aliyun DirectMail | ✅ **YES** — via Microsoft Graph Change Notifications (subscribe to /me/messages or /users/{id}/messages; JSON webhook) |

### 2b. Cross-Border Recipient Matrix Compatibility

Every provider reported **YES** to all four routing scenarios; the differences are in the caveats.

| Provider | a. Non-CN → CN | b. Non-CN → Non-CN | c. CN → Non-CN | d. CN → CN | Key Caveat |
|---|---|---|---|---|---|
| **MXtoChina** | ✅ (primary use case) | ✅ | ✅ | ✅ | Mainland-originating mail must strictly comply with regional anti-spam rules |
| **Tencent Cloud SES** | ✅ (~97% in-CN delivery) | ✅ | ✅ | ✅ | Mainland region: template human review (~1 business day); ICP filing needed for domestic lines |
| **NetEase Enterprise Mail** | ✅ (excellent) | ✅ | ✅ (overseas "green-pass" nodes) | ✅ (excellent) | Mainland outbound: strict keyword/spam screening; ICP filing needed |
| **Alibaba Enterprise Mail** | ✅ (excellent) | ✅ | ✅ ("green-pass" servers) | ✅ (exceptional) | Mainland: keyword/data-export filters; ICP filing needed |
| **SendCloud (by Sohu)** | ✅ (excellent, optimized) | ✅ | ✅ (mandatory content scanners) | ✅ (bypasses GFW) | Mainland pool requires ICP filing for domain approval |
| **Alibaba Cloud DirectMail** | ✅ (highly efficient) | ✅ | ✅ (domestic auditing applies) | ✅ (excellent) | Mainland-region account requires ICP filing |
| **M365 by 21Vianet** | ✅ | ✅ (may hit anti-spam on bulk) | ✅ (extensive compliance filtering) | ✅ (highly optimized) | Entirely in-China; ICP filing mandatory for the domain |

---

## 3. Cost Comparison

This table answers **(Q2)** cost details, free tier, and trial options, plus how billing works.

| Provider | Free Tier | Free Trial | Commercial Pricing Model | Notable Payment Constraints |
|---|---|---|---|---|
| **MXtoChina** | ❌ None | ❌ None (no public trial) | **Hybrid:** fixed monthly subscription (per sales contract) **+ pay-as-you-go overages**. Baseline includes up to **50,000 emails/month**; overages metered at cycle end. SMS priced separately by CN carrier rates. (Includes manual brand registration with Chinese ISPs.) | No self-service/casual tier — base fee disclosed only via sales contract; overages billed at end of monthly cycle |
| **Tencent Cloud SES** | ✅ **1,000 free emails** (per-account allowance) | (Free allowance serves as the trial) | **Pay-as-you-go**, daily billing cycle: **$0.00028/email** beyond the free allowance; optional **Dedicated IP at $120.00/month per IP** | International payment card required at signup; Balance ≤ 0 → API auto-suspends sending until topped up |
| **NetEase Enterprise Mail** (NetEase QiYe) | ❌ No developer free tier | ⚠️ 7-day free trial (manual; via consultation/account manager, not scriptable) | Subscription per seat/year, min **5 seats**. **Flagship (旗舰版):** ~¥200/user/yr — ¥1,000 (5-user) / ¥3,700 (20-user). **Deluxe (尊享版):** ~¥260/user/yr — ¥1,300 (5-user) / ¥4,810 (20-user). ¥1,000 ≈ $138 USD | Not pay-as-you-go; no API developer profile. Multi-year deals (e.g. "buy 3 years, get 3 free") via resellers |
| **Alibaba Enterprise Mail** | ✅ **Free Edition** (limits) — bind custom GoDaddy domain + small cluster of internal accounts | (Free Edition serves as the entry point) | Standard/Advanced Editions: fixed **annual** commitment per mailbox (~5-account baseline) | Not pay-as-you-go |
| **SendCloud (by Sohu)** | ✅ **50 emails/day** free (up to **100/day** by completing console checklist tasks) | (Free daily quota is the trial) | **Prepaid credit** system; bulk "Email Packages" (e.g., start at 10,000 emails) | ❌ No international pay-as-you-go card billing; global users must arrange **international bank wire** to top up |
| **Alibaba Cloud DirectMail** | ✅ **Lifetime free quota: 2,000 emails** (does not expire) | ⚠️ Possible 6-month trial of 10,000 / 50,000 emails (promo-dependent) | **Pay-as-you-go** after free credits, or bulk prepaid "resource plans" | New accounts capped at 2,000 emails/day (scales up with clean history) |
| **M365 by 21Vianet** | ❌ No developer free tier / no instant credit | ⚠️ 7–30 day corporate eval (~25 licenses), negotiated with a 21Vianet account manager | Enterprise subscription via direct sales / local CSP partners; localized **annual** contracts | No open Developer Program / no casual programmatic trial (unlike global M365) |

---

## 4. Detailed Breakdown by Provider

### 4.1 MXtoChina (MXflow.io — Webpower China)

- **Type:** Specialized, **Shanghai-based B2B SMTP relay *and* SMS delivery** service operated by Webpower China (Netherlands, Hong Kong, Shanghai offices). Built to help international businesses/developers reliably bypass the "Great Firewall" and deliver transactional email (invoices, password recoveries, OTPs) and marketing SMS into mainland China's local ISPs (qq.com, 163.com). Enforces SPF, DKIM, and DMARC compliance to guarantee delivery across Chinese ISPs.
- **Q1 — Indian dev registration & Python testing:** **YES, but corporate-only and via request (no self-service/sandbox).** Indian developers *can* register — but not as casual individuals; you must register as a verified corporate or professional identity.
  - **Mandatory requirements:**
    - **Corporate email account** — a business email on your own domain (generic providers like Gmail/Yahoo/Outlook are restricted unless manually whitelisted for enterprise clients).
    - **Verified domain control** — proof of ownership or admin access to the domain you plan to route through their SMTP relay.
    - **Compliance with Chinese anti-spam laws** — your application must state its intended use-case; content is audited for financial scams, restricted data, and explicit materials.
  - **Steps to sign up:**
    1. Navigate to the official site (MXflow / MXtoChina — `https://mxflow.io/about/`).
    2. Initiate contact via their developer onboarding form or email **info@mxtochina.com**.
    3. Provide your domain name, company details, and expected monthly volume.
    4. Set up the mandatory **two-factor authentication (2FA)** enforced on the Webpower framework to secure your API pipeline.
  - **Registration method (direct vs. quotation):** You **cannot** instantly spin up a self-service account — you must submit a request or a consultation/quotation inquiry first, via **info@mxtochina.com** or **support@mxtochina.com**. The platform then manually registers your brand name with localized Chinese ISPs to whitelist your traffic and optimize real-time deliverability.
- **Q2 — Cost/free tier/trial:** **No free tier, no public trial.** Pricing follows a **hybrid subscription model** — a baseline fixed monthly subscription fee (disclosed via a sales contract tailored to corporate requirements) **plus pay-as-you-go volume overages**:
  - **Base monthly plan:** fixed monthly fee (per sales contract).
  - **Included baseline volume:** up to **50,000 emails/month**.
  - **Overage pricing:** volumes exceeding 50,000 emails/month are metered and billed as a variable charge at the end of the monthly billing cycle.
  - **SMS tracking/delivery:** priced separately based on localized mainland-China mobile-carrier rates.
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** GoDaddy domain usable, but standard SPF/DKIM/MX is *insufficient on its own* — your brand must be registered directly with Chinese ISPs to whitelist outbound templates.
  - **Email sending:** Domain-level auth means dynamic "From" addresses work; but anonymous bulk traffic, spam-like dynamic variations, and unauthorized marketing are prohibited under Chinese anti-spam rules; content is heavily audited.
  - **Inbound parse:** Not supported. Maintain inbound MX routing through an independent third-party mail handler (Mailgun/SendGrid/Postmark) or self-hosted Python IMAP/aiosmtpd/Haraka.
- **Cross-border:** All four scenarios supported; Mainland-originating mail must comply with regional regulatory/anti-spam standards.

### 4.2 Tencent Cloud SES (Simple Email Service)

- **Type:** Developer-first transactional cloud email (API 3.0 + SMTP) on Tencent Cloud International; deep routing into Chinese ISPs (~97% in-China delivery).
- **Q1 — Indian dev registration & Python testing:** **YES — direct, self-service signup (no quotation or sales contact required).** The entire onboarding is self-service: once your card is added and ID verified, you can instantly log in, activate the SES product, verify your domain, and start sending. Requirements:
  - **Valid email / Google account** (for the credentials).
  - **Indian mobile number** (+91) — active, to receive the SMS OTP verification.
  - **International payment method** — a credit/debit card enabled for international transactions to verify the billing account.
  - **KYC identity verification** — a scanned Indian government ID (e.g. passport, driver's license) for individual accounts; review usually takes **2–4 business days**.
  - **Domain ownership** — DNS access to add SPF/DKIM/DMARC records.
  - Registration steps: sign up on the Tencent Cloud International console → select **India** as country/region → pass the mobile OTP check → add payment card → complete ID verification in the Account Center. Then test in Python via the API Explorer or `tencentcloud-sdk-python`.
- **Q2 — Cost/free tier/trial:** **Free tier — every account is entitled to 1,000 free emails.** Beyond the free allowance, flexible **daily pay-as-you-go** billing at **$0.00028 per email**. Optional **dedicated IP** (to protect sender reputation) is a flat **$120.00/month per IP**. If balance hits zero, outbound sending auto-suspends until topped up.
- **Q3 — Restrictions & mandatory steps:**
  - **Identity gating:** Individual/Enterprise Identity Verification required before the SES console activates — upload Indian government ID (passport/license) or business cert. Manual review ~2–4 business days.
  - **Domain verification (GoDaddy):** Generate values in the SES panel and map the DNS records — **SPF and DKIM** (the core identity records), plus DMARC and MX — in GoDaddy DNS. Any failed entry blocks activation. **Tencent advises verifying a third-level subdomain (e.g. `mail.ims.com`) rather than your root corporate domain**, to keep transactional email traffic isolated from organizational business communication. Supports whole-domain/subdomain authorization; no per-mailbox verification.
  - **Email sending:** New domains get strict daily caps; transactional/marketing templates must pass console review before bulk sending. **Dynamic "From" supported (domain-level auth):** once the sending subdomain passes SPF + DKIM verification, the authorization applies globally to the entire domain — you can pass any username prefix (e.g. `ankit-000@`, `ankit-111@`) in the `FromEmailAddress` parameter of `SendEmail`/`BatchSendEmail` (or via SMTP) without verifying individual local parts, provided the domain suffix matches your verified environment.
  - **Inbound parse:** Not supported — Tencent SES is architected as an **outbound-only email-push service** (no MX parsing engine, no inbound webhooks). To capture replies, set the `ReplyToAddresses` parameter to an external inbox (a personal or corporate mailbox); replies bypass Tencent entirely and route straight to that inbox. For programmatic inbound handling, route inbound MX to a third-party (Mailgun Inbound Parse) or a Python aiosmtpd listener.
  - **Cross-border/ICP:** Domestic Mainland infrastructure requires ICP Filing (Beian) with MIIT.

### 4.3 NetEase Enterprise Mail (网易企业邮箱 / NetEase QiYe)

- **Type:** Corporate mailbox/collaboration suite (like Google Workspace / M365), not a transactional API. "NetEase QiYe" is the native Chinese brand name of the same product. China's largest email infrastructure network.
- **Q1 — Indian dev registration & Python testing:** **YES, but with heavy infrastructure limitations.** An Indian developer *can* register, subject to two hard requirements:
  - **Chinese phone number (+86):** the system mandates a real-name-authenticated Chinese mobile to generate the **16-digit Client Authorization Password**. You cannot bind third-party SMTP/IMAP clients using your normal login password — the Client Authorization Password is required.
  - **Real-name verification:** the admin account requires **corporate- or passport-based** real-name verification before you can fully lift the external IP restriction (`ERR.LOGIN.IPDENY`). Passport-based verification means a Chinese business license is *not* strictly required, but the +86 number is.
  - **Official caveat:** NetEase support documentation states the platform is optimized for domestic operations and is explicitly **not suitable for independent overseas foreign-trade or global developer operations** due to these firewall/IP hurdles.
- **Registration flow (direct vs. quotation):** You can initiate registration **directly online** for standard tiers — retail packs of **5 to 100 users** are structured via the NetEase Mobile Price Matrix Page. But to actually activate service and **lift international network filters**, you must submit your details to a dedicated enterprise consultant through a **"Purchase Consultation" (购买咨询)** request workflow (or via an authorized reseller).
- **Q2 — Cost/free tier/trial:** **No developer free tier.** A **7-day free trial** exists but is manual (consultation/account-manager provisioned, not scriptable). Commercial pricing is a strict per-seat/year subscription with a **5-user minimum**:
  - **Flagship Edition (旗舰版):** ~¥200 RMB/user/year — **¥1,000/year** (5-user pack), **¥3,700/year** (20-user pack).
  - **Deluxe Edition (尊享版):** ~¥260 RMB/user/year — **¥1,300/year** (5-user pack), **¥4,810/year** (20-user pack).
  - **Promotions:** multi-year commitments (e.g. 3-year tiers) often unlock deep reseller/agent discounts or **"Buy 3 Years, Get 3 Years Free"** extensions. (¥1,000 ≈ $138 USD.) Not pay-as-you-go; no API developer profile.
- **Q3 — Restrictions & mandatory steps:**
  - **Custom domain verification:** **Fully supported.** Map a custom domain (e.g. `@mail.ims.com`) by configuring standard **MX, SPF, and DKIM** records at your DNS registrar (GoDaddy), which points your corporate domain at the NetEase transmission clusters. (For reliable *Mainland* delivery the domain should also carry an **ICP Filing (备案)** with MIIT, or domestic telecom nodes may throttle/drop the traffic.)
  - **Email sending / dynamic "From":** **No native dynamic/wildcard "From" support.** Every unique "From" prefix must map to a valid, pre-configured mailbox seat, user account, or structural alias (unregistered → SMTP 550). NetEase's own documentation directs developers who need programmatic, high-volume dynamic outbound pipelines to use dedicated transactional relays (e.g. **SendGrid** or similar) rather than the fixed enterprise mailbox system. Workarounds: Account/Alias Management API, or pivot to Tencent SES / Aliyun DirectMail.
  - **Inbound parse:** **Not supported** — NetEase is a traditional SaaS office platform with only conventional inbound *rules* (auto-forwarding, auto-replies, public-account push routing). It cannot convert incoming raw MIME streams into a real-time HTTP POST callback to a destination URL. For a true inbound pipeline, route your MX records through a transactional parser such as **SendGrid Inbound Parse** or the **Brevo Inbound Parse Webhook** suite, or use Python IMAP IDLE polling.
- **Cross-border:** All four supported; Mainland outbound subject to keyword/spam screening; overseas "green-pass" nodes clear foreign firewalls.

### 4.4 Alibaba Enterprise Mail (阿里企业邮箱 / Aliyun Mail)

- **Type:** Corporate workforce mailbox suite managed via Alibaba Cloud International.
- **Q1 — Indian dev registration & Python testing:** **YES, with programmatic restrictions.** Register an Alibaba Cloud International account with India as billing hub (Indian mobile + credit card), tie your GoDaddy domain. You can use `smtplib`/`imaplib`, but it is **not** an open bulk mailer — automation must use a **Client Security Password** generated in the web UI, not your account password.
- **Q2 — Cost/free tier/trial:** **Free Edition available (with limits)** — binds a custom GoDaddy domain and provisions a small cluster of internal accounts for free. Paid **Standard/Advanced Editions** use fixed **annual** commitments computed per mailbox (~5-account baseline minimum). Not pay-as-you-go.
- **Q3 — Restrictions & mandatory steps:**
  - **Real-name gating:** Individual/Enterprise Real-Name Verification (Indian passport/license/tax cert) before domain binding unlocks.
  - **Domain verification (GoDaddy):** Add **4 records — MX, SPF (TXT), CNAME, DKIM**. Propagation failure keeps mailbox blocked.
  - **Email sending:** **No programmatic wildcard sending** — every prefix must be pre-provisioned as user/group/alias (arbitrary dynamic addresses → sender mismatch error). Workaround: API alias provisioning, or pivot to Tencent SES / SendCloud.
  - **Inbound parse:** No inbound webhook. Use Python IMAP IDLE or MX split to Mailgun/SendGrid/Postmark.
  - **Cross-border/ICP:** Mainland-hosted org requires ICP Filing (备案) with MIIT.
- **Note:** The source recommends **Alibaba Cloud DirectMail** instead if you need dynamic domain-wide sending + a built-in free tier.

### 4.5 SendCloud (by Sohu)

- **Type:** Developer-first transactional + marketing cloud email (spun off from Sohu); REST API (/apiv2/mail/send) + SMTP; optimized for delivery into Chinese ISPs (QQ, 163, Sina).
- **Q1 — Indian dev registration & Python testing:** **YES, with constraints.** Register with international/Indian developer details (Indian mobile for verification). Account starts in restricted **Sandbox/Trial mode** — sending limited to manually whitelisted "test recipients" until identity vetting completes. Python scripts via REST/SMTP work immediately (against whitelisted recipients).
- **Q2 — Cost/free tier/trial:** **Free trial tier — 50 emails/day** (increasable to **100/day** by completing console checklist tasks like verifying registration email and binding a domain). Commercial: **prepaid credit** system with bulk "Email Packages" (start ~10,000 emails). **No international pay-as-you-go card billing** — global users must contact financial support to arrange an international bank wire.
- **Q3 — Restrictions & mandatory steps:**
  - **Real-name gating:** Real-Name Identity Verification (business registration or passport scan) to send to real, un-whitelisted recipients.
  - **Domain verification (GoDaddy):** Map **3 records — SPF (TXT), DKIM (TXT), tracking CNAME**; domain stays "pending" until auto-detected. Domain-level auth (no per-prefix registration); dynamic "From" supported.
  - **Email sending:** **Mandatory template review + From-address configuration** before live sends; unreviewed raw HTML via API → 400 Bad Request.
  - **Inbound parse:** Outbound-only webhooks; route inbound MX to Mailgun/SendGrid/Postmark or a Python aiosmtpd listener.
  - **Cross-border/ICP:** Mainland China infrastructure pool requires ICP Filing (备案) or the domain won't be approved on domestic lines.

### 4.6 Alibaba Cloud DirectMail

- **Type:** Outbound-only transactional email engine on Alibaba Cloud International (built on the infra powering Alibaba e-commerce).
- **Q1 — Indian dev registration & Python testing:** **YES.** Alibaba Cloud International fully supports Indian personal/corporate details (Indian mobile + credit/debit card). Map the GoDaddy domain and test immediately with `alibabacloud-dm20151123` SDK or SMTP.
- **Q2 — Cost/free tier/trial:** **Lifetime free quota of 2,000 emails** (no expiry) for development testing. Possible **6-month trial** of 10,000 or 50,000 emails (promo-dependent). After credits: **pay-as-you-go** (per successfully handled email) or bulk prepaid "resource plans."
- **Q3 — Restrictions & mandatory steps:**
  - **Real-name gating:** Individual/Enterprise Real-Name Verification (Indian passport/license or incorporation filings).
  - **Domain verification (GoDaddy):** Configure **4 records — SPF, DKIM, DMARC, MX**; domain locked until all propagate.
  - **Email sending:** **No dynamic wildcard senders** — hard limit of **100 registered sender addresses per account**, each pre-verified in console (arbitrary dynamic addresses → auth error). New accounts capped at **2,000 emails/day**, auto-scaling up (to millions/day) with clean sending history. Workaround for dynamic needs: pivot to Tencent SES / SendCloud.
  - **Inbound parse:** Outbound-only; uses **Alibaba Cloud Message Service (MNS)** event webhooks for outbound metrics. Route inbound MX to a third-party (Mailgun) or a Python aiosmtpd/Haraka server.
  - **Cross-border/ICP:** Mainland-region account requires ICP Filing (备案) with MIIT.

### 4.7 Microsoft 365 operated by 21Vianet

- **Type:** Sovereign, China-isolated instance of Microsoft 365 / Exchange Online, hosted entirely inside Mainland China (endpoints microsoftonline.cn / portal.azure.cn / chinacloudapi.cn).
- **Q1 — Indian dev registration & Python testing:** **NO.** No international self-service/sandbox. Requires a **Mainland China Business License** (unified social credit code) or localized corporate credentials, plus a **+86 mobile**. Cannot register on microsoftonline.cn with Indian-only details.
- **Q2 — Cost/free tier/trial:** **No developer free tier / no instant credit** (unlike the global M365 Developer Program's free 90-day sandbox). Enterprise subscription via direct sales / local CSP partners. **7–30 day corporate eval trials (~25 licenses)** must be negotiated with a 21Vianet account manager. Localized **annual** enterprise contracts thereafter.
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** Add GoDaddy domain with MX/SPF/DKIM, but the domain must have an **ICP Filing (备案)** with MIIT or Mainland telecom filters/severs the traffic.
  - **Email sending:** Exchange Online is **not an open SMTP relay** — every sender prefix must be a licensed User / Shared Mailbox / provisioned Alias in the Azure China Portal (unprovisioned → SMTP 550). Dynamic senders workaround: Graph API alias provisioning (**≤400 aliases per mailbox**) via chinacloudapi.cn, or bypass outbound to Tencent SES / Aliyun DirectMail.
  - **Inbound parse:** ✅ **Supported** — the only provider here with it, via **Microsoft Graph Change Notifications** (subscribe to /me/messages or /users/{id}/messages; receive a JSON webhook with validationToken + message ID, then fetch/parse the MIME body). Python must request OAuth tokens from the isolated **chinacloudapi.cn** endpoint (not global Entra).
- **Cross-border:** All four supported; high-volume/bulk to non-CN may trigger Microsoft outbound anti-spam blocks; outbound from 21Vianet undergoes extensive compliance filtering.

---

## Quick Takeaways (from the source files)

- **Easiest for an Indian developer to sign up & test with Python today:** **Alibaba Cloud DirectMail** and **Tencent Cloud SES** (both fully open with Indian details; SendCloud and Alibaba Enterprise Mail also work but with sandbox/mailbox constraints).
- **Best free entry point:** **Alibaba Cloud DirectMail** (2,000-email lifetime free quota) and **Tencent Cloud SES** (1,000 free emails), then **SendCloud** (50–100 emails/day free) and **Alibaba Enterprise Mail** (Free Edition).
- **Cannot be self-served (must request onboarding), but open to Indian *corporate* identities — no Chinese identity required:** **MXtoChina** (register as a verified corporate/professional entity via info@mxtochina.com; hybrid pricing with a 50k-emails/month baseline).
- **Registrable but heavily gated for Indian developers (needs a real-name-authenticated +86 China mobile; passport-based verification works, so no Chinese business license is strictly required):** **NetEase Enterprise Mail (NetEase QiYe)** — but officially not recommended for overseas/global developer use.
- **Cannot be self-served with Indian details (need Chinese identity/business):** **M365 by 21Vianet**.
- **Support truly dynamic "From" addresses (domain-level auth):** **MXtoChina, Tencent Cloud SES, SendCloud** — YES. All others require pre-provisioned senders.
- **Native inbound parse:** Only **M365 by 21Vianet** (via Microsoft Graph). Every other provider needs an inbound MX split to a third party (Mailgun/SendGrid/Postmark) or a self-hosted Python IMAP/aiosmtpd listener.
- **Universal compliance requirement:** Any Mainland-China-hosted sending path requires an **ICP Filing (备案) with MIIT** for the domain.
