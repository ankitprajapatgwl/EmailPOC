# Chinese Email Providers Comparison for mail sending and monitoring

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


---

## 1. Short Description of Each Provider

- **MXtoChina (MXflow.io):** A specialized, **Shanghai-based B2B SMTP relay *and* SMS delivery** service operated by Webpower China (offices in Netherlands, Hong Kong, Shanghai). Purpose-built to help international businesses/developers bypass the "Great Firewall" and reliably deliver transactional email (invoices, password recoveries, OTPs) and marketing SMS into mainland China's local ISPs. Enforces SPF/DKIM/DMARC compliance. **Open to verified corporate/professional identities (including Indian) — but via request/quotation only; no instant self-service signup.**

- **Tencent Cloud SES:** A developer-first transactional cloud email API/SMTP service on Tencent Cloud International. Domain-level authentication, dynamic senders, outbound event webhooks, and deep routing into Chinese ISPs (~97% in-China delivery). **Open to Indian developers.**

- **NetEase Enterprise Mail (网易企业邮箱 / NetEase QiYe):** A corporate mailbox/collaboration suite (like Google Workspace / M365), not a transactional API. Strict per-mailbox sender authorization. **Registrable by an Indian developer, but with heavy infrastructure limitations** — mandates a real-name-authenticated **Chinese (+86) mobile number** to generate the 16-digit Client Authorization Password, plus corporate- or passport-based real-name verification to lift external IP restrictions (`ERR.LOGIN.IPDENY`). Officially stated to be optimized for domestic operations and *not* suitable for overseas/global developer use.

- **Alibaba Enterprise Mail (Aliyun Mail):** A **collaborative corporate mailbox for human employees** (NOT a programmatic API — that role belongs to Alibaba Cloud DirectMail), managed via Alibaba Cloud International. Registrable with Indian details on the **International Site** under a functional region such as **Singapore** (Alibaba closed its Mumbai/India data centers on **15 July 2024**, so India is no longer an independent cloud zone). Strict per-mailbox sender verification. **Paid per-user seat subscription — starts ~$2.87/user/month, 3-seat minimum, 500 GB storage/user; no developer free tier** (use DirectMail for a free quota).

- **SendCloud (by Sohu):** A Chinese developer-first transactional + marketing cloud email platform (spun off from Sohu), operating under **sendcloud.net** (entirely separate from the European logistics platform sendcloud.com). Domain-level auth, dynamic senders, inbound parse webhooks, and outbound events; optimized for delivery into Chinese ISPs. **Registration strictly requires a +86 Mainland China mobile for OTP — Indian (+91) numbers are not accepted at signup.** Free tier: 10 emails/day.

- **Alibaba Cloud DirectMail:** An outbound-only transactional email engine on Alibaba Cloud International. Registrable with Indian details (India region closed Jul 2024 — deploy in Singapore); includes a free tier of **2,000 emails/day**, but requires each sender address to be pre-registered (no wildcard/dynamic senders). PAYG billing at **$0.29 per 1,000 emails** after the free tier.

- **Microsoft 365 operated by 21Vianet:** The sovereign, China-isolated instance of Microsoft 365 (Exchange Online) hosted entirely inside Mainland China. Not an open SMTP relay; no native inbound parse — inbound email routing requires **Power Automate (21Vianet)** to monitor mailboxes and POST structured payloads to a webhook (or Graph Change Notifications for event-driven MIME fetch). **Requires a legally established onshore Chinese entity (WFOE/JV) + Chinese Business License + ICP License/Recordal from MIIT — Indian developers cannot register independently.**

---

## 2. Functionality Comparison

### 2a. Core Capabilities & Developer Access

This table answers: **(Q1)** Can an Indian developer register & test with Python? · Domain verification without per-sender verification · Custom dynamic "From" addresses · **(Q3)** Inbound Parse webhook support.

| Provider | Service Type | Indian Dev Register + Python Test? (Q1) | Domain Verification w/o Sender Verification | Custom Dynamic "From" Addresses | Inbound Parse via Webhook (Q3) |
|---|---|---|---|---|---|
| **MXtoChina** | B2B SMTP relay + SMS delivery | ⚠️ YES (corporate-only, no self-service) — Indian devs *can* register, but only as a verified corporate/professional identity (not casual individuals). Requires a business email on your own domain, verified domain control, and a stated compliance use-case. Onboard via request/quotation to info@mxtochina.com; 2FA enforced. | ✅ YES — SPF/DKIM/DMARC domain-level; no per-inbox verification | ✅ YES — dynamic From accepted & signed under verified domain | ❌ NO — outbound tracking only; workaround: route inbound MX to Mailgun/SendGrid/Postmark or self-host aiosmtpd/Haraka |
| **Tencent Cloud SES** | Developer transactional API/SMTP | ✅ YES — **direct self-service signup (no quotation/sales contact)**; Indian details + Indian mobile OTP (+91) + international payment card + KYC govt-ID (2–4 day review); email/Google SSO; instant Python test via API Explorer or `tencentcloud-sdk-python` | ✅ YES — domain-level auth via **SPF + DKIM** (Tencent advises a third-level subdomain, e.g. `mail.ims.com`, over the root domain); once verified, any prefix under it sends without per-address verification | ✅ YES — dynamic From via API 3.0 (SendEmail) or SMTP | ❌ NO — outbound-only push service; workaround: use `ReplyToAddresses` to an external inbox, or SendGrid/Mailgun inbound parse / self-host aiosmtpd/Haraka |
| **NetEase Enterprise Mail** (NetEase QiYe) | Corporate mailbox suite | ⚠️ YES (heavy limitations) — requires a real-name-authenticated **+86 China mobile** (to issue the 16-digit Client Authorization Password) + corporate- or **passport**-based real-name verification to lift IP restrictions (`ERR.LOGIN.IPDENY`). Officially not suitable for overseas/global dev use. | ❌ NO — every sender must be a provisioned mailbox/group/alias (else SMTP 550) | ❌ NO — blocked; NetEase directs high-volume dynamic pipelines to a transactional relay (SendGrid / Tencent SES / Aliyun DirectMail) | ❌ NO — traditional inbound rules only; workaround: route MX to SendGrid/Brevo Inbound Parse, or IMAP IDLE polling |
| **Alibaba Enterprise Mail** | Corporate mailbox suite (human employees) | ⚠️ YES (with restrictions) — Alibaba Cloud **International Site** account w/ Indian details, functional region **Singapore** (India cloud zone closed 15 Jul 2024); uses Client Security Password, not an open bulk mailer | ❌ NO — sender prefix must be pre-registered user/group/alias | ❌ NO — every "From" must map to an explicit **billable account/alias** in the Admin Portal; workaround: `ModifyMailAddress`/account-creation APIs (capped per-tenant), or pivot to Tencent SES / SendCloud | ❌ NO — admin events only; workaround: IMAP polling or MX split to SendGrid/Postmark/Mailgun |
| **SendCloud (by Sohu)** | Developer transactional/marketing cloud | ⚠️ YES (heavily constrained) — registration **requires a +86 Mainland China mobile number** (Indian +91 not accepted at signup); account starts in restricted Sandbox/Trial mode (only whitelisted test recipients); corporate identity verification required to lift sandbox; 10 emails/day free | ✅ YES — domain-level (SPF/DKIM/DMARC/MX + tracking CNAME); no per-prefix registration | ✅ YES — dynamic From via HTTP REST API (/apiv2/mail/send) or SMTP | ✅ YES — via SendCloud's **Routing/Inbound Parse** component; automatically extracts MIME components and forwards structured payload to an external webhook URL you specify |
| **Alibaba Cloud DirectMail** | Outbound-only transactional engine | ✅ YES — Alibaba Cloud Intl w/ Indian details; `alibabacloud-dm20151123` SDK or SMTP | ❌ NO — each exact sender prefix must be pre-registered (else InvalidSenderAddress) | ❌ NO — workaround: pre-provisioned sender pool via OpenAPI SDK (quota-limited), or pivot to Tencent SES / SendCloud | ❌ NO — uses MNS event webhooks for outbound only; workaround: MX split to third-party parser or self-host aiosmtpd/Haraka |
| **M365 by 21Vianet** | Sovereign Exchange Online (China) | ❌ NO — requires a legally established onshore Chinese entity (WFOE/JV) + Chinese Business License + ICP License/Recordal from MIIT + +86 mobile; cannot register on microsoftonline.cn with Indian-only details | ❌ NO — Exchange Online not an open relay; sender must be licensed user/shared mailbox/alias (else SMTP 550) | ❌ NO — workaround: Graph API alias provisioning (≤400 aliases/mailbox) via chinacloudapi.cn, or bypass outbound to **Azure Communication Services**, Tencent SES, or Aliyun DirectMail | ⚠️ **NO native inbound parse** — requires **Power Automate (21Vianet)**: trigger on mailbox arrival → parse Sender/Body/Attachments → POST to external webhook URL; or use Microsoft Graph Change Notifications (subscribe to /me/messages or /users/{id}/messages) for event-driven MIME fetch |

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
| **MXtoChina** | ❌ None | ❌ None (no public trial) | **Custom quotation only** — no public pricing catalog or standard monthly packages listed on mxflow.io. Structure (per contract): fixed monthly base + pay-as-you-go overages; indicative baseline ~**50,000 emails/month**; overages metered at cycle end. SMS priced separately by CN carrier rates. Contact **support@mxtochina.com** or **contact@mxtochina.com** for a quote. (Includes manual brand registration with Chinese ISPs.) | No self-service/casual tier — pricing disclosed only via custom sales contract |
| **Tencent Cloud SES** | ✅ **1,000 free emails** (per-account allowance) | (Free allowance serves as the trial) | **Pay-as-you-go**, daily billing cycle: **$0.00028/email** beyond the free allowance; optional **Dedicated IP at $120.00/month per IP** | International payment card required at signup; Balance ≤ 0 → API auto-suspends sending until topped up |
| **NetEase Enterprise Mail** (NetEase QiYe) | ❌ No developer free tier | ⚠️ 7-day free trial (manual; via consultation/account manager, not scriptable) | Subscription per seat/year, min **5 seats**. **Flagship (旗舰版):** ~¥200/user/yr (**~$27.60**) — ¥1,000 / **$138** (5-user) / ¥3,700 / **$510.60** (20-user). **Deluxe (尊享版):** ~¥260/user/yr (**~$35.88**) — ¥1,300 / **$179.40** (5-user) / ¥4,810 / **$663.78** (20-user). *(Conversion: ¥1 ≈ $0.138 USD)* | Not pay-as-you-go; no API developer profile. Multi-year deals (e.g. "buy 3 years, get 3 free") via resellers |
| **Alibaba Enterprise Mail** | ❌ No developer free tier (use **DirectMail** for Alibaba's free quota) | ❌ None documented (self-service purchase online) | **Per-user seat subscription** — starts ~**$2.87/user/month**, **3-seat minimum**, **500 GB storage/user**; higher **Standard/Advanced** editions billed **annually** | Not pay-as-you-go; direct self-service purchase (quotation only for large/custom migrations); intl credit card / **PayPal** / gateway |
| **SendCloud (by Sohu)** | ✅ **10 emails/day** free (sandbox/trial tier) | (Free daily quota is the trial) | **Base monthly platform fee + tiered pay-as-you-go:** ¥59 CNY / **~$8.14** per month for 0–10,000 emails; +¥5.6 CNY / **~$0.77** per 1,000 for 10,001–50,000; +¥5.3 CNY / **~$0.73** per 1,000 for 50,001–100,000 | ❌ No international pay-as-you-go card billing; global users must arrange **international bank wire** to top up |
| **Alibaba Cloud DirectMail** | ✅ **Free tier: 2,000 emails/day** | N/A (free daily quota is the trial) | **Pay-as-you-go:** **$0.29 per 1,000 emails** beyond the free tier; **Prepaid 6-month resource packages:** 50k emails = $13.05 · 500k = $121.80 · 1M = $230.55; **Dedicated IP add-on:** $128/IP/month | New accounts capped at 2,000 emails/day (scales up with clean history) |
| **M365 by 21Vianet** | ❌ No developer free tier / no instant credit | ⚠️ 7–30 day corporate eval (~25 licenses), negotiated with a 21Vianet account manager | Enterprise subscription via 21Vianet portal (`21vbluecloud.com/o365-landing/`) or local CSP; all pricing billed in **CNY (¥)** under localized **annual** contracts. Per-user/month (annual): **O365 E1** ¥66.06 / **~$9.12** · **M365 Enterprise Apps** ¥79.27 / **~$10.94** · **O365 E3** ¥151.93 / **~$20.97** · **M365 E3** ¥192.65 / **~$26.59** | No open Developer Program / no casual programmatic trial (unlike global M365) |

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
    1. Go to the primary onboarding engine at **mxflow.io** and click **"Get Started"** or **"Schedule a call today"** to submit your corporate email infrastructure details. (The button routes to a manual review and scheduling funnel — there is no public self-service login creation screen.)
    2. Provide your domain name, company details, and expected monthly volume.
    3. Complete **domain whitelisting** per the SMTP Relay Guide (step 3: "Whitelist your domain"), align SPF/DKIM/SMTP security variables, and establish mandatory **two-factor authentication (2FA)** enforced through the Webpower engine.
  - **Registration method (direct vs. quotation):** You **cannot** instantly spin up a self-service account — you must submit a consultation or quotation request first, via **info@mxtochina.com**, **support@mxtochina.com**, or **contact@mxtochina.com**. The platform then manually registers your brand with Chinese ISPs (Tencent, NetEase, etc.) to whitelist your traffic before initiating delivery.
- **Q2 — Cost/free tier/trial:** **No free tier, no public trial.** There are **no standardized or publicly listed pricing tiers** — the entire rate structure is determined on a **custom quotation basis** tailored to your enterprise volume and infrastructure requirements. No public pricing catalog or standard monthly packages appear on the mxflow.io website; pricing is disclosed only after contacting their support team. General structure (per sales contract):
  - **Base monthly plan:** fixed monthly fee (disclosed via custom contract).
  - **Included baseline volume:** up to **50,000 emails/month** (indicative figure from quoted contracts).
  - **Overage pricing:** volumes exceeding the contracted baseline are metered and billed as a variable charge at the end of the monthly billing cycle.
  - **SMS tracking/delivery:** priced separately based on localized mainland-China mobile-carrier rates.
  - **To obtain pricing:** contact **support@mxtochina.com** or **contact@mxtochina.com** with your volume metrics and domain details.
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** GoDaddy domain usable, but standard SPF/DKIM/MX is *insufficient on its own* — your brand must be registered directly with Chinese ISPs to whitelist outbound templates.
  - **Email sending:** Domain-level auth means dynamic "From" addresses work; but anonymous bulk traffic, spam-like dynamic variations, and unauthorized marketing are prohibited under Chinese anti-spam rules; content is heavily audited.
  - **Inbound parse:** Not supported — mxflow.io is a strictly outbound transaction engine. Their documented 4-step workflow is: *"You relay to us (Outbound) → We authenticate → We deliver in-country → You track results."* No webhooks or inbound parse documentation exist on their platform. Maintain inbound MX routing through an independent third-party mail handler (Mailgun/SendGrid/Postmark) or self-hosted Python IMAP/aiosmtpd/Haraka.
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
  - **Flagship Edition (旗舰版):** ~¥200 RMB/user/year (**~$27.60**) — **¥1,000/year / ~$138** (5-user pack), **¥3,700/year / ~$510.60** (20-user pack).
  - **Deluxe Edition (尊享版):** ~¥260 RMB/user/year (**~$35.88**) — **¥1,300/year / ~$179.40** (5-user pack), **¥4,810/year / ~$663.78** (20-user pack).
  - **Promotions:** multi-year commitments (e.g. 3-year tiers) often unlock deep reseller/agent discounts or **"Buy 3 Years, Get 3 Years Free"** extensions. (¥1,000 ≈ $138 USD, i.e. ¥1 ≈ $0.138 — the conversion rate used throughout this document.) Not pay-as-you-go; no API developer profile.
- **Q3 — Restrictions & mandatory steps:**
  - **Custom domain verification:** **Fully supported.** Map a custom domain (e.g. `@mail.ims.com`) by configuring standard **MX, SPF, and DKIM** records at your DNS registrar (GoDaddy), which points your corporate domain at the NetEase transmission clusters. (For reliable *Mainland* delivery the domain should also carry an **ICP Filing (备案)** with MIIT, or domestic telecom nodes may throttle/drop the traffic.)
  - **Email sending / dynamic "From":** **No native dynamic/wildcard "From" support.** Every unique "From" prefix must map to a valid, pre-configured mailbox seat, user account, or structural alias (unregistered → SMTP 550). NetEase's own documentation directs developers who need programmatic, high-volume dynamic outbound pipelines to use dedicated transactional relays (e.g. **SendGrid** or similar) rather than the fixed enterprise mailbox system. Workarounds: Account/Alias Management API, or pivot to Tencent SES / Aliyun DirectMail.
  - **Inbound parse:** **Not supported** — NetEase is a traditional SaaS office platform with only conventional inbound *rules* (auto-forwarding, auto-replies, public-account push routing). It cannot convert incoming raw MIME streams into a real-time HTTP POST callback to a destination URL. For a true inbound pipeline, route your MX records through a transactional parser such as **SendGrid Inbound Parse** or the **Brevo Inbound Parse Webhook** suite, or use Python IMAP IDLE polling.
- **Cross-border:** All four supported; Mainland outbound subject to keyword/spam screening; overseas "green-pass" nodes clear foreign firewalls.

### 4.4 Alibaba Enterprise Mail (阿里企业邮箱 / Aliyun Mail)

- **Type:** A **collaborative corporate mailbox for human employees**, managed via Alibaba Cloud International. **Critical distinction: Alibaba Enterprise Mail ≠ Alibaba Cloud DirectMail.** Enterprise Mail is the human-facing collaborative mailbox suite; **DirectMail** (§4.6) is the developer API/SMTP transactional engine for programmatic outbound sending. Choose Enterprise Mail for internal staff mailboxes, DirectMail for app-generated email.
- **Data-center note:** Alibaba Cloud **closed its local Indian (Mumbai) data centers on 15 July 2024.** India is no longer an independent cloud zone, but Indian developers can still register on the **International Site** and run mail services from another region such as **Singapore / Singapore-International**.
- **Q1 — Indian dev registration & Python testing:** **YES, with programmatic restrictions.** Register an Alibaba Cloud International account (International Site) choosing an available functional region (e.g. Singapore), then tie your GoDaddy domain. You can use `smtplib`/`imaplib`, but it is **not** an open bulk mailer — automation must use a **Client Security Password** generated in the web UI, not your account login password.
  - **Requirements:**
    - **Domain ownership** — you must own a domain and have full authority to modify its authoritative DNS zone file.
    - **Real-name verification** — mandatory identity verification before any mail infrastructure can be used.
    - **International payment method** — a valid international credit card, **PayPal**, or accepted payment gateway tied to an international billing address.
  - **Steps to register:**
    1. Go to the **Alibaba Cloud International Registration Portal** (`https://account.alibabacloud.com/register/intl_register.htm`).
    2. Choose your default currency and billing territory.
    3. Complete Identity Verification in the Account Center — **Passport/ID** for an individual account, or **corporate business-registry documents** for a business account.
    4. In the console, activate the **Alibaba Mail** (or DirectMail) resource suite.
- **Registration method (direct vs. quotation):** **Direct self-service.** Standard tiers are purchased directly through the console marketplace by mapping out the required mail seats — **no quotation/sales contact needed.** Quotation/sales requests are reserved only for complex custom migrations or massive enterprise commitments beyond standard subscription ceilings.
- **Q2 — Cost/free tier/trial:** **No developer free tier.** Billing is a **per-user seat subscription** — base price **starts at ~$2.87 / user / month**, with a **minimum purchase of 3 seats** and **500 GB storage per user**. Higher **Standard/Advanced** editions carry fixed **annual** per-mailbox commitments. **Not pay-as-you-go.** (If you need a free quota or dynamic domain-wide sending, use **Alibaba Cloud DirectMail** instead — see §4.6.)
- **Q3 — Restrictions & mandatory steps:**
  - **Real-name gating:** Individual/Enterprise Real-Name Verification (Indian passport/ID, or corporate registry docs) before domain binding unlocks.
  - **Domain verification (GoDaddy):** Add **4 DNS records — two TXT records (one SPF, one domain-ownership validation), one MX record, and one CNAME record.** All must resolve to "Active/Verified" before sending is enabled; propagation failure keeps the mailbox blocked.
  - **Email sending / dynamic "From":** **NO dynamic/wildcard senders.** Alibaba Mail does **not** support random dynamic prefix matching — every sending address must map to an **explicit, billable provisioning account or a defined alias created in the Admin Control Portal** (arbitrary addresses → sender-mismatch error). Workaround: programmatically instantiate senders via the **`ModifyMailAddress` / account-creation APIs**, but this is bound by **strict per-tenant maximum account limits**; or pivot to Tencent SES / SendCloud for true dynamic sending.
  - **Inbound parse:** No inbound webhook. Use Python IMAP IDLE polling or an MX split to Mailgun/SendGrid/Postmark.
  - **Cross-border/ICP:** A Mainland-hosted org requires ICP Filing (备案) with MIIT.
- **Note:** Use **Alibaba Cloud DirectMail** instead if you need dynamic domain-wide sending plus a built-in free tier.

### 4.5 SendCloud (by Sohu)

- **Type:** Developer-first transactional + marketing cloud email (spun off from Sohu), operating under **sendcloud.net** (entirely separate from the European e-commerce logistics platform sendcloud.com); REST API (/apiv2/mail/send) + SMTP; optimized for delivery into Chinese ISPs (QQ, 163, Sina).
- **Q1 — Indian dev registration & Python testing:** **YES, but heavily constrained — registration requires a +86 Mainland China mobile number.** The registration form strictly requires a **+86 Chinese mobile** for SMS/voice OTP verification; Indian (+91) numbers are not accepted at signup. Steps:
  1. Go to the SendCloud Registration page (sendcloud.net/register).
  2. Input a valid **+86 Chinese phone number** to pass the real-name verification gateway.
  3. Complete the dynamic behavioral captcha.
  4. Once inside the console, the free tier gives **10 emails/day** for sandbox testing.
  5. To send to unwhitelisted recipients or increase quota beyond the sandbox, complete a **corporate identity verification** (business registration or passport scan).
  - Python scripts via REST/SMTP work immediately once the account is provisioned (against whitelisted test recipients in sandbox; all recipients after identity verification).
- **Registration method:** **Direct self-service** — no quotation/sales contact needed to register or activate the free tier. Quotation/enterprise support is only needed when monthly volume exceeds standard commercial tiers.
- **Q2 — Cost/free tier/trial:** **Free tier — 10 emails/day** (sandbox/trial tier, activated immediately after registration). Commercial billing uses a **base monthly platform fee + tiered pay-as-you-go volume model:**
  - **0–10,000 emails:** ¥59 CNY/month (base plan) — **~$8.14/month**
  - **10,001–50,000 emails:** +¥5.6 CNY per 1,000 emails — **~$0.77 per 1,000**
  - **50,001–100,000 emails:** +¥5.3 CNY per 1,000 emails — **~$0.73 per 1,000**
  - **No international pay-as-you-go card billing** — global users must contact financial support to arrange an **international bank wire** to top up.
- **Q3 — Restrictions & mandatory steps:**
  - **Real-name gating:** Corporate identity verification (business registration or passport scan) to send to real, un-whitelisted recipients and lift sandbox limits.
  - **Domain verification (GoDaddy):** Map **5 records — SPF (TXT), DKIM (TXT), DMARC (TXT), MX, and tracking CNAME**; domain stays "pending" until all records propagate and are auto-detected. Domain-level auth (no per-prefix registration); dynamic "From" supported.
  - **Email sending:** **Mandatory template review + From-address configuration** before live sends; unreviewed raw HTML via API → 400 Bad Request. Once the sending domain passes SPF + DKIM verification, any prefix under that domain can be passed dynamically as the From address.
  - **Inbound parse:** ✅ **Supported** — via SendCloud's built-in **Routing/Inbound Parse component**. The engine handles user replies sent to your custom domain, extracts the core MIME components, and forwards the structured contents programmatically to an **external webhook URL** you specify. This means you do not need to route inbound MX to a third-party parser for basic inbound handling.
  - **Cross-border/ICP:** Mainland China infrastructure pool requires ICP Filing (备案) or the domain won't be approved on domestic lines.

### 4.6 Alibaba Cloud DirectMail

- **Type:** Outbound-only transactional email engine on Alibaba Cloud International (built on the infra powering Alibaba e-commerce).
- **Q1 — Indian dev registration & Python testing:** **YES.** Alibaba Cloud International fully supports Indian personal/corporate details (Indian mobile + credit/debit card). Map the GoDaddy domain and test immediately with `alibabacloud-dm20151123` SDK or SMTP.
- **Q2 — Cost/free tier/trial:** **Free tier of 2,000 emails/day** (active immediately on account creation; no separate activation needed). After the free daily quota: **pay-as-you-go at $0.29 per 1,000 emails** (default billing method). For bulk volume, **prepaid 6-month resource packages** are available at a lower effective rate:
  - **50,000 emails:** $13.05
  - **500,000 emails:** $121.80
  - **1,000,000 emails:** $230.55
  - **Dedicated IP add-on** (to protect sender reputation by isolating from the shared IP pool): **$128/IP/month**.
- **Q3 — Restrictions & mandatory steps:**
  - **Real-name gating:** Individual/Enterprise Real-Name Verification (Indian passport/license or incorporation filings).
  - **Domain verification (GoDaddy):** Configure **4 records — SPF, DKIM, DMARC, MX**; domain locked until all propagate.
  - **Email sending:** **No dynamic wildcard senders** — hard limit of **100 registered sender addresses per account**, each pre-verified in console (arbitrary dynamic addresses → auth error). New accounts capped at **2,000 emails/day**, auto-scaling up (to millions/day) with clean sending history. Workaround for dynamic needs: pivot to Tencent SES / SendCloud.
  - **Inbound parse:** Outbound-only; uses **Alibaba Cloud Message Service (MNS)** event webhooks for outbound metrics. Route inbound MX to a third-party (Mailgun) or a Python aiosmtpd/Haraka server.
  - **Cross-border/ICP:** Mainland-region account requires ICP Filing (备案) with MIIT.

### 4.7 Microsoft 365 operated by 21Vianet

- **Type:** Sovereign, China-isolated instance of Microsoft 365 / Exchange Online, hosted entirely inside Mainland China (endpoints microsoftonline.cn / portal.azure.cn / chinacloudapi.cn).
- **Q1 — Indian dev registration & Python testing:** **NO.** No international self-service/sandbox. As an Indian developer (or any entity outside Mainland China), you cannot register for an independent 21Vianet tenant. Eligibility strictly requires:
  - A legally established **onshore Chinese legal entity** — e.g. a Wholly Foreign-Owned Enterprise (**WFOE**) or Joint Venture (**JV**) — registered inside China.
  - A valid **Chinese Business License** (unified social credit code).
  - An **ICP License / Recordal** from the Ministry of Industry and Information Technology (**MIIT**) for any public-facing service.
  - A **+86 Mainland China mobile** number.
  - Cannot register on microsoftonline.cn with Indian-only details.
  - If you satisfy the above onshore legal criteria, sign up via the localized **21Vianet portal** (`https://www.21vbluecloud.com/o365-landing/`); otherwise, coordinate with a **regional Microsoft account manager** or submit a business request to **21Vianet Presales Support**.
- **Q2 — Cost/free tier/trial:** **No developer free tier / no instant credit** (unlike the global M365 Developer Program's free 90-day sandbox). Enterprise subscription via the **21Vianet portal** or local CSP partners. **7–30 day corporate eval trials (~25 licenses)** must be negotiated with a 21Vianet account manager. All pricing is billed exclusively in **Chinese Yuan (CNY / ¥)** under localized **annual** contracts; regional tax additions apply. Current tier pricing (per user/month, annual commitment; USD conversion at ¥1 ≈ $0.138):

  | Plan | Price (¥/user/month) | Price (~USD/user/month) | Key Features |
  |---|---|---|---|
  | Office 365 E1 | ¥66.06 (~₹760) | ~$9.12 | Web/Mobile apps, 50 GB mailbox, 1 TB OneDrive |
  | Microsoft 365 Enterprise Apps | ¥79.27 (~₹915) | ~$10.94 | Desktop Office suite, 1 TB OneDrive |
  | Office 365 E3 | ¥151.93 (~₹1,750) | ~$20.97 | Desktop apps, 100 GB mailbox, advanced compliance |
  | Microsoft 365 E3 | ¥192.65 (~₹2,220) | ~$26.59 | Full O365 E3 + Advanced Threat & Identity Protection |
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** Add GoDaddy domain with MX/SPF/DKIM, but the domain must have an **ICP Filing (备案)** with MIIT or Mainland telecom filters/severs the traffic.
  - **Email sending:** Exchange Online is **not an open SMTP relay** — every sender prefix must be a licensed User / Shared Mailbox / provisioned Alias in the Azure China Portal (unprovisioned → SMTP 550). Microsoft 365 is **not designed** for transactional bulk email with dynamic/randomized sub-prefixes. Dynamic senders workaround: Graph API alias provisioning (**≤400 aliases per mailbox**) via chinacloudapi.cn, or bypass outbound to **Azure Communication Services**, Tencent SES, or Aliyun DirectMail.
  - **Inbound parse:** ⚠️ **No native inbound parse** — no built-in SMTP-to-HTTP webhook that automatically POSTs structured MIME components to a destination URL. To programmatically handle incoming mail, orchestrate a **Power Automate (operated by 21Vianet)** flow: (1) trigger on mailbox arrival, (2) parse Sender / Body / Attachments objects, (3) POST structured payload to your external webhook URL. Alternatively, use **Microsoft Graph Change Notifications** (subscribe to `/me/messages` or `/users/{id}/messages`; receive a JSON webhook with `validationToken` + message ID, then fetch/parse the MIME body on each event). Python must request OAuth tokens from the isolated **chinacloudapi.cn** endpoint (not global Entra).
- **Cross-border:** All four supported; high-volume/bulk to non-CN may trigger Microsoft outbound anti-spam blocks; outbound from 21Vianet undergoes extensive compliance filtering.

---

## Quick Takeaways (from the source files)

- **Easiest for an Indian developer to sign up & test with Python today:** **Alibaba Cloud DirectMail** and **Tencent Cloud SES** (both fully open with Indian details; Alibaba Enterprise Mail also works but with mailbox constraints). **SendCloud requires a +86 Chinese mobile for signup — Indian numbers are not accepted.**
- **Best free entry point:** **Alibaba Cloud DirectMail** (2,000 emails/day free tier; PAYG at $0.29/1,000 emails after that) and **Tencent Cloud SES** (1,000 free emails one-time allowance), then **SendCloud** (10 emails/day free — but requires +86 mobile to register). *(Alibaba **Enterprise** Mail has no free tier — it is a paid per-seat product from ~$2.87/user/month, 3-seat minimum; use DirectMail for Alibaba's free quota.)*
- **Cannot be self-served (must request onboarding), but open to Indian *corporate* identities — no Chinese identity required:** **MXtoChina** (register as a verified corporate/professional entity via clicking "Get Started" / "Schedule a call today" on mxflow.io, or email info@mxtochina.com / contact@mxtochina.com; custom-quotation pricing only — no public tiers; indicative baseline ~50k emails/month).
- **Registrable but heavily gated — require a +86 China mobile:** **NetEase Enterprise Mail (NetEase QiYe)** (passport-based verification works, so no Chinese business license strictly required — but officially not recommended for overseas/global developer use) and **SendCloud** (strictly requires +86 for signup OTP; no workaround documented).
- **Cannot be self-served with Indian details (need Chinese identity/business):** **M365 by 21Vianet**.
- **Support truly dynamic "From" addresses (domain-level auth):** **MXtoChina, Tencent Cloud SES, SendCloud** — YES. All others require pre-provisioned senders.
- **Native inbound parse:** **SendCloud** (via built-in Routing/Inbound Parse webhook). **M365 by 21Vianet** has no native inbound parse — requires **Power Automate (21Vianet)** for webhook-style routing or Microsoft Graph Change Notifications for event-driven MIME fetch (OAuth via chinacloudapi.cn). Every other provider needs an inbound MX split to a third party (Mailgun/SendGrid/Postmark) or a self-hosted Python IMAP/aiosmtpd listener.
- **Universal compliance requirement:** Any Mainland-China-hosted sending path requires an **ICP Filing (备案) with MIIT** for the domain.
