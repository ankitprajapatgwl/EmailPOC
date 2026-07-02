# Chinese Email Providers — Comparison for a Python Send & Monitoring System

> **Scope & sources:** Every provider was evaluated against the same set of questions for an **Indian developer** using **Indian details** and an **Indian GoDaddy domain**, building a **Python** send-and-monitoring system.
>
> **Providers covered:**
> 1. MXtoChina (MXflow.io — Webpower China)
> 2. Tencent Cloud SES (Simple Email Service)
> 3. NetEase Enterprise Mail (网易企业邮箱)
> 4. Alibaba Enterprise Mail (阿里企业邮箱 / Aliyun Mail)
> 5. SendCloud (by Sohu)
> 6. Alibaba Cloud DirectMail
> 7. NetEase QiYe (网易企业邮箱 — native brand name of NetEase Enterprise Mail)
> 8. Microsoft 365 operated by 21Vianet
>
> **Note:** Per the source files, **NetEase Enterprise Mail** and **NetEase QiYe** are the *same product* (English name vs. native Chinese brand name). They are listed separately because they were supplied as separate files, and their answers are identical.

---

## 1. Short Description of Each Provider

- **MXtoChina (MXflow.io):** A specialized, managed authenticated transactional/marketing relay operated by Webpower China (offices in Netherlands, Hong Kong, Shanghai). Purpose-built to push mail through China's firewall filters into local ISPs. **Managed enterprise service — no self-service signup.**

- **Tencent Cloud SES:** A developer-first transactional cloud email API/SMTP service on Tencent Cloud International. Domain-level authentication, dynamic senders, outbound event webhooks, and deep routing into Chinese ISPs (~97% in-China delivery). **Open to Indian developers.**

- **NetEase Enterprise Mail (网易企业邮箱):** A corporate mailbox/collaboration suite (like Google Workspace / M365), not a transactional API. Strict per-mailbox sender authorization. **Requires Chinese identity to register.**

- **Alibaba Enterprise Mail (Aliyun Mail):** A corporate workforce mailbox suite managed via Alibaba Cloud International. Strict per-mailbox sender verification, but registrable with Indian details (with programmatic restrictions). Has a free edition.

- **SendCloud (by Sohu):** A Chinese developer-first transactional + marketing cloud email platform (spun off from Sohu). Domain-level auth, dynamic senders, outbound webhooks, optimized for delivery into Chinese ISPs. **Open to Indian developers with constraints; has a free daily quota.**

- **Alibaba Cloud DirectMail:** An outbound-only transactional email engine on Alibaba Cloud International. Registrable with Indian details, includes a lifetime free quota, but requires each sender address to be pre-registered (no wildcard/dynamic senders).

- **NetEase QiYe:** Native Chinese brand of NetEase Enterprise Mail — identical policies (corporate suite, Chinese identity required, per-mailbox sending).

- **Microsoft 365 operated by 21Vianet:** The sovereign, China-isolated instance of Microsoft 365 (Exchange Online) hosted entirely inside Mainland China. Not an open SMTP relay, but uniquely offers inbound parsing via Microsoft Graph Change Notifications. **Requires Chinese business credentials to register.**

---

## 2. Functionality Comparison

### 2a. Core Capabilities & Developer Access

This table answers: **(Q1)** Can an Indian developer register & test with Python? · Domain verification without per-sender verification · Custom dynamic "From" addresses · **(Q3)** Inbound Parse webhook support.

| Provider | Service Type | Indian Dev Register + Python Test? (Q1) | Domain Verification w/o Sender Verification | Custom Dynamic "From" Addresses | Inbound Parse via Webhook (Q3) |
|---|---|---|---|---|---|
| **MXtoChina** | Managed transactional/marketing relay | ❌ NO — no self-service/sandbox; must request enterprise onboarding via corporate offices, you cannot register as a casual individual developer. You must register as a verified corporate or professional identity. | ✅ YES — SPF/DKIM/DMARC domain-level; no per-inbox verification | ✅ YES — dynamic From accepted & signed under verified domain | ❌ NO — outbound tracking only; workaround: route inbound MX to Mailgun/SendGrid/Postmark or self-host aiosmtpd/Haraka |
| **Tencent Cloud SES** | Developer transactional API/SMTP | ✅ YES — Indian details, email/Google SSO, instant Python test via API Explorer or `tencentcloud-sdk-python` | ✅ YES — authorize whole domain/subdomain via TXT/CNAME/MX; any address under it | ✅ YES — dynamic From via API 3.0 (SendEmail) or SMTP | ❌ NO — outbound events only; workaround: SendGrid/Mailgun inbound parse or self-host aiosmtpd/Haraka |
| **NetEase Enterprise Mail** | Corporate mailbox suite | ❌ NO — requires +86 China mobile + domestic Chinese business license | ❌ NO — every sender must be a provisioned mailbox/group/alias (else SMTP 550) | ❌ NO — blocked; workaround: sub-account API bridge, or pivot to NetEase Transactional Mail / Tencent SES / Aliyun DirectMail | ❌ NO — corporate events only; workaround: IMAP IDLE polling or MX split to Mailgun/SendGrid |
| **Alibaba Enterprise Mail** | Corporate mailbox suite | ⚠️ YES (with restrictions) — Alibaba Cloud Intl account w/ Indian details; uses Client Security Password, not an open bulk mailer | ❌ NO — sender prefix must be pre-registered user/group/alias | ❌ NO — sender mismatch block; workaround: API alias provisioning, or pivot to Tencent SES / SendCloud | ❌ NO — admin events only; workaround: IMAP polling or MX split to SendGrid/Postmark/Mailgun |
| **SendCloud (by Sohu)** | Developer transactional/marketing cloud | ⚠️ YES (with constraints) — register w/ Indian mobile, but starts in Sandbox mode (sending only to whitelisted test recipients until vetted) | ✅ YES — domain-level (SPF/DKIM/MX); no per-prefix registration | ✅ YES — dynamic From via HTTP REST API (/apiv2/mail/send) or SMTP | ❌ NO — outbound events only; workaround: MX to SendGrid/Postmark/Mailgun or self-host aiosmtpd/Haraka |
| **Alibaba Cloud DirectMail** | Outbound-only transactional engine | ✅ YES — Alibaba Cloud Intl w/ Indian details; `alibabacloud-dm20151123` SDK or SMTP | ❌ NO — each exact sender prefix must be pre-registered (else InvalidSenderAddress) | ❌ NO — workaround: pre-provisioned sender pool via OpenAPI SDK (quota-limited), or pivot to Tencent SES / SendCloud | ❌ NO — uses MNS event webhooks for outbound only; workaround: MX split to third-party parser or self-host aiosmtpd/Haraka |
| **NetEase QiYe** | Corporate mailbox suite (same as NetEase Ent. Mail) | ❌ NO — requires +86 China mobile + domestic Chinese business license (Unified Social Credit Code) | ❌ NO — every address must be a provisioned account/alias (else SMTP 550) | ❌ NO — workaround: Account/Alias Management API, or NetEase Transactional Mail Solution | ❌ NO — SSO/AD-sync/unread-count APIs only; workaround: IMAP IDLE, or MX split to Cloudflare Email Routing/Mailgun/aiosmtpd |
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
| **NetEase QiYe** | ✅ (domestic authority) | ✅ | ✅ (smart cross-border nodes) | ✅ (exceptional) | Mainland accounts: keyword/compliance scrubbing; ICP filing needed |
| **M365 by 21Vianet** | ✅ | ✅ (may hit anti-spam on bulk) | ✅ (extensive compliance filtering) | ✅ (highly optimized) | Entirely in-China; ICP filing mandatory for the domain |

---

## 3. Cost Comparison

This table answers **(Q2)** cost details, free tier, and trial options, plus how billing works.

| Provider | Free Tier | Free Trial | Commercial Pricing Model | Notable Payment Constraints |
|---|---|---|---|---|
| **MXtoChina** | ❌ None | ❌ None (no public trial) | Custom enterprise, volume-dependent contractual pricing (includes manual brand registration with Chinese ISPs) | No pay-as-you-go / no casual developer tier |
| **Tencent Cloud SES** | ❌ No continuous free tier | ❌ No free trial credits for outgoing email | **Pay-as-you-go**, daily billing cycle, tiered volume model | Balance ≤ 0 → API auto-suspends sending until topped up |
| **NetEase Enterprise Mail** | ❌ No developer free tier | ⚠️ 7-day free trial (manual; via consultation/account manager, not scriptable) | Fixed enterprise packages; min **5 mailboxes** from **~¥1,000 RMB (~$138 USD)/year** | Not pay-as-you-go; no API developer profile |
| **Alibaba Enterprise Mail** | ✅ **Free Edition** (limits) — bind custom GoDaddy domain + small cluster of internal accounts | (Free Edition serves as the entry point) | Standard/Advanced Editions: fixed **annual** commitment per mailbox (~5-account baseline) | Not pay-as-you-go |
| **SendCloud (by Sohu)** | ✅ **50 emails/day** free (up to **100/day** by completing console checklist tasks) | (Free daily quota is the trial) | **Prepaid credit** system; bulk "Email Packages" (e.g., start at 10,000 emails) | ❌ No international pay-as-you-go card billing; global users must arrange **international bank wire** to top up |
| **Alibaba Cloud DirectMail** | ✅ **Lifetime free quota: 2,000 emails** (does not expire) | ⚠️ Possible 6-month trial of 10,000 / 50,000 emails (promo-dependent) | **Pay-as-you-go** after free credits, or bulk prepaid "resource plans" | New accounts capped at 2,000 emails/day (scales up with clean history) |
| **NetEase QiYe** | ❌ No developer free tier | ⚠️ 7-day free trial (manual, sales-desk provisioned) | Fixed package; entry **5 mailboxes ~¥1,000 RMB (~$138 USD)/year** | Not pay-as-you-go; no API developer profile |
| **M365 by 21Vianet** | ❌ No developer free tier / no instant credit | ⚠️ 7–30 day corporate eval (~25 licenses), negotiated with a 21Vianet account manager | Enterprise subscription via direct sales / local CSP partners; localized **annual** contracts | No open Developer Program / no casual programmatic trial (unlike global M365) |

---

## 4. Detailed Breakdown by Provider

### 4.1 MXtoChina (MXflow.io — Webpower China)

- **Type:** Managed, authenticated transactional/marketing relay optimized to bypass China's firewall filters into local ISPs (qq.com, 163.com). Operated by Webpower China (Netherlands, Hong Kong, Shanghai offices).
- **Q1 — Indian dev registration & Python testing:** **NO.** No open self-service registration or developer sandbox. Accounts are strictly vetted; you must contact their corporate offices to request an enterprise onboarding evaluation.
- **Q2 — Cost/free tier/trial:** **No free tier, no public trial.** Pricing is customized on an enterprise, volume-dependent contractual basis (includes manually registering your brand with Chinese ISPs like Tencent and NetEase). No pay-as-you-go developer model.
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** GoDaddy domain usable, but standard SPF/DKIM/MX is *insufficient* — your brand must be registered directly with Chinese ISPs to whitelist outbound templates.
  - **Email sending:** Domain-level auth means dynamic "From" addresses work; but anonymous bulk traffic, spam-like dynamic variations, and unauthorized marketing are prohibited under Chinese anti-spam rules; content is heavily audited.
  - **Inbound parse:** Not supported. Maintain inbound MX routing through an independent third-party mail handler (Mailgun/SendGrid/Postmark) or self-hosted Python IMAP/aiosmtpd/Haraka.
- **Cross-border:** All four scenarios supported; Mainland-originating mail must comply with regional regulatory/anti-spam standards.

### 4.2 Tencent Cloud SES (Simple Email Service)

- **Type:** Developer-first transactional cloud email (API 3.0 + SMTP) on Tencent Cloud International; deep routing into Chinese ISPs (~97% in-China delivery).
- **Q1 — Indian dev registration & Python testing:** **YES.** Register with Indian personal/enterprise details via email or Google SSO. Immediate Python testing after adding the GoDaddy domain, using the API Explorer or `tencentcloud-sdk-python`.
- **Q2 — Cost/free tier/trial:** **No continuous free tier and no free trial credits.** Daily pay-as-you-go billing on a tiered volume model. If balance hits zero, outbound sending auto-suspends until topped up.
- **Q3 — Restrictions & mandatory steps:**
  - **Identity gating:** Individual/Enterprise Identity Verification required before the SES console activates — upload Indian government ID (passport/license) or business cert. Manual review ~2–4 business days.
  - **Domain verification (GoDaddy):** Generate values in the SES panel and map **4 records — SPF, DKIM, DMARC, MX** — in GoDaddy DNS. Any failed entry blocks activation. Supports whole-domain/subdomain authorization; no per-mailbox verification.
  - **Email sending:** New domains get strict daily caps; transactional/marketing templates must pass console review before bulk sending. Dynamic "From" supported.
  - **Inbound parse:** Not supported — route inbound MX to a third-party (Mailgun Inbound Parse) or a Python aiosmtpd listener.
  - **Cross-border/ICP:** Domestic Mainland infrastructure requires ICP Filing (Beian) with MIIT.

### 4.3 NetEase Enterprise Mail (网易企业邮箱)

- **Type:** Corporate mailbox/collaboration suite (like Google Workspace / M365), not a transactional API. China's largest email infrastructure network.
- **Q1 — Indian dev registration & Python testing:** **NO.** No self-service onboarding/sandbox for international entities. Requires a **+86 Mainland China mobile number** for verification and a **domestic Chinese business license / localized legal representative** to sign the provisioning contract.
- **Q2 — Cost/free tier/trial:** **No developer free tier.** A **7-day free trial** exists but is manual (via Online Consultation System / activation desk, account-manager provisioned). Commercial minimum is a **5-mailbox package starting ~¥1,000 RMB (~$138 USD)/year**.
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** GoDaddy domain can be added with MX/SPF/DKIM, but the domain must have an **ICP Filing (备案)** with MIIT or Mainland telecom nodes drop it.
  - **Email sending:** Strict sender identity checks — every sender must be a provisioned mailbox/group/alias (unregistered → SMTP 550). Each user needs a **16-digit Client Authorization Code** for third-party Python clients. No dynamic/spoofed "From" (workarounds: sub-account API bridge, or pivot to NetEase Transactional Mail Solution / Tencent SES / Aliyun DirectMail).
  - **Inbound parse:** No webhook framework — use Python IMAP IDLE polling or split inbound MX to Mailgun/aiosmtpd.
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

### 4.7 NetEase QiYe (网易企业邮箱)

- **Type:** Native Chinese brand name of **NetEase Enterprise Mail** — identical operational policies, infrastructure gates, and platform rules. Corporate email hosting/collaboration suite, not a developer SMTP relay.
- **Q1 — Indian dev registration & Python testing:** **NO.** No self-service onboarding/sandbox for international individuals. Requires **+86 Mainland China mobile** for SMS verification and a **domestic Chinese business license (Unified Social Credit Code)** to sign the provisioning contract.
- **Q2 — Cost/free tier/trial:** **No developer free tier / no pay-as-you-go API profile.** **7-day free trial** is manual (sales-desk, account-manager reviewed — not scriptable). Entry commercial package: **5 mailboxes ~¥1,000 RMB (~$138 USD)/year**.
- **Q3 — Restrictions & mandatory steps:**
  - **Domain verification:** Add GoDaddy domain with MX/SPF/DKIM, but the domain must hold an **ICP Filing (备案)** with MIIT or Mainland telecom drops/throttles the traffic.
  - **Email sending:** Not an open relay — every outbound address must be an explicitly created account/alias; each needs a **16-digit Client Authorization Code** as the SMTP password. No dynamic/unprovisioned "From" (workaround: Account/Alias Management API, or NetEase Transactional Mail Solution).
  - **Inbound parse:** No inward webhooks (only SSO/AD-sync/unread-count APIs). Use Python IMAP IDLE polling or split inbound MX to Cloudflare Email Routing / Mailgun / aiosmtpd.
- **Cross-border:** All four supported; Mainland outbound gets keyword/compliance scrubbing; smart overseas "green-pass" nodes for outbound-to-global.

### 4.8 Microsoft 365 operated by 21Vianet

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
- **Best free entry point:** **Alibaba Cloud DirectMail** (2,000-email lifetime free quota), then **SendCloud** (50–100 emails/day free) and **Alibaba Enterprise Mail** (Free Edition).
- **Cannot be self-served with Indian details (need Chinese identity/business):** **MXtoChina**, **NetEase Enterprise Mail / NetEase QiYe**, **M365 by 21Vianet**.
- **Support truly dynamic "From" addresses (domain-level auth):** **MXtoChina, Tencent Cloud SES, SendCloud** — YES. All others require pre-provisioned senders.
- **Native inbound parse:** Only **M365 by 21Vianet** (via Microsoft Graph). Every other provider needs an inbound MX split to a third party (Mailgun/SendGrid/Postmark) or a self-hosted Python IMAP/aiosmtpd listener.
- **Universal compliance requirement:** Any Mainland-China-hosted sending path requires an **ICP Filing (备案) with MIIT** for the domain.
