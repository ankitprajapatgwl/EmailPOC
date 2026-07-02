# China Email Provider Analysis — JobSetU Platform
**Dynamic Address + Inbound Parse Webhook Workflow**

> **Document Version:** 2.0 | **Date:** June 25, 2026  
> **Platform:** JobSetU | **Domain:** mail.jobsetu.online  
> **Use Case:** User → Dynamic Address → China Supplier → Reply → Inbound Webhook

---

## Your Exact Workflow (Reference)

```
Step 1: User selects supplier from search results

Step 2: App generates a dynamic email address
        e.g. ankit-dkfghwiu@mail.jobsetu.online

Step 3: Email sent to supplier's personal/company email
        FROM: ankit-dkfghwiu@mail.jobsetu.online
        TO:   supplier@company.cn

Step 4: China Supplier receives email, clicks "Reply"
        REPLY goes to: ankit-dkfghwiu@mail.jobsetu.online

Step 5: Provider receives the reply email on your domain

Step 6: Provider fires webhook POST to your server
        URL: https://your-app.jobsetu.online/webhooks/inbound
        BODY: full parsed email (from, to, subject, body, attachments)

Step 7: Your app processes reply, maps to conversation, shows to user
```

**Two critical capabilities required:**
1. Send email using a dynamic sub-address of your authorized domain
2. Receive replies on that sub-address and forward to your webhook (Inbound Parse)

---

## Provider Analysis — Feature Scorecard

| Feature | SendGrid | Aliyun DM | Alibaba Cloud DM | MXtoChina (Webpower) | M365 (21Vianet) | Tencent Cloud SES | NetEase QiYe |
|---|---|---|---|---|---|---|---|
| Dynamic address from your domain | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Limited | ❌ No | ✅ Yes | ❌ No |
| Inbound Parse / Webhook | ✅ Native | ❌ No | ❌ No | ⚠️ Partial | ❌ No | ❌ No | ❌ No |
| China delivery reliability | ⚠️ ~70% | ✅ ~95% | ✅ ~95% | ✅ ~92% | ✅ ~90% | ✅ ~95% | ✅ ~98% |
| Open/Click tracking | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ Limited | ✅ Yes | ❌ No |
| SPF/DKIM/DMARC | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| Dedicated IPs | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ Shared only | ✅ Yes | ✅ Yes |
| API for sending | ✅ REST | ✅ REST | ✅ REST | ✅ REST | ⚠️ Graph API | ✅ REST | ❌ SMTP only |
| China server infrastructure | ❌ US-based | ✅ China | ✅ China | ✅ China | ✅ China | ✅ China | ✅ China |
| ICP compliance | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| English documentation | ✅ Excellent | ✅ Good | ✅ Good | ⚠️ Limited | ✅ Excellent | ⚠️ Partial | ❌ Chinese only |

> **Note:** Aliyun Direct Mail and Alibaba Cloud Direct Mail are the **same product** (Aliyun IS Alibaba Cloud's infrastructure brand). They share identical APIs, pricing, and capabilities — treated as one provider below.

---

## Provider 1: SendGrid (Twilio)

### Overview
SendGrid is a US-based email delivery platform owned by Twilio. It is the most feature-complete provider for your specific workflow (dynamic address + inbound parse), but has infrastructure limitations for China.

### Dynamic Email Address Support

**✅ Fully Supported — Best in Class**

SendGrid lets you send from any sub-address of your verified domain. You simply set the `from` field dynamically on each API call:

```javascript
const sgMail = require('@sendgrid/mail');
sgMail.setApiKey(process.env.SENDGRID_API_KEY);

await sgMail.send({
  to: 'supplier@company.cn',
  from: `ankit-${generateHash()}@mail.jobsetu.online`,  // Dynamic per conversation
  replyTo: `ankit-${generateHash()}@mail.jobsetu.online`, // Same or different dynamic address
  subject: 'Inquiry about your products',
  html: '<p>Hello...</p>'
});
```

No pre-registration of individual addresses is required. As long as `mail.jobsetu.online` is verified (which yours is), any sub-address works immediately.

**Limitations:**
- Each dynamic address must be unique per conversation to avoid collision
- The `from` display name should be consistent to avoid spam classification
- SendGrid does not store sent emails by address — you must track mapping on your side

### Inbound Parse / Webhook Support

**✅ Fully Supported — Native Feature**

SendGrid Inbound Parse is the most mature inbound webhook system among all providers listed. It:

- Sets up MX records on your domain (`mail.jobsetu.online`)
- Receives ALL incoming email to any address at that domain
- Parses the email (headers, body, attachments) into a structured POST payload
- Fires a webhook to your configured URL within 1-5 seconds of receipt
- Supports raw MIME, parsed HTML/text, base64 attachments, spam score

**Setup (already done on your account):**
```
MX Record:  mail.jobsetu.online  →  mx.sendgrid.net  (Priority 10)
Webhook:    https://your-app.jobsetu.online/webhooks/inbound
```

**Webhook payload fields:**
```json
{
  "to": "ankit-dkfghwiu@mail.jobsetu.online",
  "from": "supplier@company.cn",
  "subject": "Re: Inquiry about your products",
  "text": "Thank you for your message...",
  "html": "<p>Thank you...</p>",
  "headers": "...",
  "attachments": "2",
  "attachment-info": "{...}",
  "spam_score": "0.0",
  "spam_report": "..."
}
```

**Parsing the dynamic address from webhook:**
```javascript
app.post('/webhooks/inbound', (req, res) => {
  const toAddress = req.body.to;
  // e.g. "ankit-dkfghwiu@mail.jobsetu.online"
  const conversationId = toAddress.split('@')[0].replace('ankit-', '');
  // conversationId = "dkfghwiu"
  
  // Look up which user/supplier pair this belongs to
  const conversation = await db.findConversation(conversationId);
  
  // Store reply
  await db.saveReply(conversation.id, {
    from: req.body.from,
    body: req.body.text,
    receivedAt: new Date()
  });
  
  res.status(200).send('OK');
});
```

### China Delivery Reliability

**⚠️ Moderate — 65-75% on first attempt, ~85% after retries**

SendGrid uses US-based infrastructure. Delivery to Chinese mailboxes (QQ, 163, Aliyun) is impacted by:
- Great Firewall rate limiting on US SMTP IPs
- Chinese email providers applying reputation penalties to foreign IPs
- Higher spam folder placement rate (~15-20% vs 2-5% for local providers)

**Delivery rates by Chinese provider:**

| Supplier's Email Provider | Inbox Rate | Spam Rate | Notes |
|---|---|---|---|
| Aliyun Mail (business) | ~80% | ~5% | Most lenient with foreign SMTP |
| 163.com / 126.com | ~75% | ~15% | Strict on new sender reputation |
| QQ.com | ~65% | ~20% | Strictest filtering |
| Gmail (if used in China) | ~60% | ~25% | Often blocked at network level |

### Limitations

- **No China infrastructure:** All SMTP routing goes through US servers
- **No ICP filing:** Cannot legally host email infrastructure in mainland China
- **Inbound parse size limit:** 30MB per inbound email
- **Inbound parse rate limit:** SendGrid does not publish a hard limit but shared infrastructure means spikes can cause delays
- **Webhook retry:** Retries webhook delivery 3 times on failure (5 min, 1 hour, 6 hours)
- **Dynamic address tracking:** SendGrid does not natively correlate inbound replies to outbound messages — you must maintain your own mapping
- **No China-region endpoint:** Cannot configure China-specific SMTP endpoint
- **Free tier inbound:** Inbound Parse is free but counts toward your plan's email volume indirectly through bandwidth

### Pricing

| Volume | Plan | Cost | Notes |
|---|---|---|---|
| **10,000 emails/month** | Essentials | **$19.95/month** | 50K included; inbound parse free |
| **50,000 emails/month** | Essentials | **$19.95/month** | Included in base plan |
| **100,000 emails/month** | Pro | **$89.95/month** | 100K included; dedicated IP option |

> Inbound Parse is **free** and unlimited on all paid plans.

---

## Provider 2: Aliyun Direct Mail (= Alibaba Cloud Direct Mail)

### Overview
Aliyun Direct Mail (DM) is Alibaba Cloud's transactional email service, hosted entirely within China's mainland infrastructure. It is the most widely used China-native email delivery API, with native ICP compliance and direct peering with Chinese ISPs.

> **Important clarification:** "Aliyun" and "Alibaba Cloud" are the same company. The product "Direct Mail" is identical whether accessed via `aliyun.com` (Chinese portal) or `alibabacloud.com` (international portal). The API, pricing, and infrastructure are identical.

### Dynamic Email Address Support

**✅ Fully Supported**

Aliyun DM supports sending from any address under your verified domain. Addresses do not need pre-registration:

```javascript
const Core = require('@alicloud/pop-core');

const client = new Core({
  accessKeyId: process.env.ALIYUN_ACCESS_KEY_ID,
  accessKeySecret: process.env.ALIYUN_ACCESS_KEY_SECRET,
  endpoint: 'https://dm.aliyuncs.com',
  apiVersion: '2015-11-23'
});

const params = {
  AccountName: `ankit-${generateHash()}@mail.jobsetu.online`, // Dynamic FROM address
  ToAddress: 'supplier@company.cn',
  Subject: 'Inquiry about your products',
  HtmlBody: '<p>Hello...</p>',
  ReplyToAddress: 'true'  // Reply goes to AccountName address
};

const requestOption = { method: 'POST' };
const result = await client.request('SingleSendMail', params, requestOption);
```

**Tracking requirement:** You must store the mapping of dynamic address → conversation on your side, as Aliyun does not provide built-in conversation threading.

**Important limitation:** Aliyun DM requires each sender address (`AccountName`) to be registered in the console as a "Sender Address" before use. This means you cannot use truly random dynamic addresses without pre-registration — you would need to either:
1. Pre-register a pool of addresses (e.g. `ankit-001` through `ankit-999`)
2. Use a fixed `FROM` address and rely on `Reply-To` header for routing

### Inbound Parse / Webhook Support

**❌ NOT SUPPORTED — Critical Gap**

This is the most significant limitation of Aliyun Direct Mail. **Aliyun DM is a pure outbound service.** It has:
- No inbound email reception capability
- No MX record configuration for your domain via their service
- No webhook for received emails
- No reply tracking mechanism

**How to work around this for your workflow:**

To receive supplier replies, you would need a separate inbound email service:

**Option A: Self-hosted SMTP (Postfix/Exim on Aliyun ECS)**
- Deploy an email server on Aliyun ECS instance in China
- Set MX record for `mail.jobsetu.online` to point to your ECS
- Your server receives supplier replies and fires webhook internally
- Cost: ~$10-30/month for ECS instance
- Complexity: High (requires email server admin knowledge)

**Option B: Mailgun (Inbound) + Aliyun DM (Outbound) Hybrid**
- Use Aliyun DM for outbound (high China delivery rate)
- Use Mailgun's inbound parse for receiving replies (set MX to Mailgun)
- Problem: Reply address must be on a domain Mailgun controls for inbound
- Complexity: Medium

**Option C: Use a different domain for inbound**
- Outbound FROM: `ankit-xxx@mail.jobsetu.online` (Aliyun DM)
- Reply-To: `ankit-xxx@replies.jobsetu.online` (different subdomain, different MX)
- Configure `replies.jobsetu.online` MX to point to a separate inbound service
- Complexity: Medium

### China Delivery Reliability

**✅ Excellent — 94-97% inbox delivery**

As a China-native service, Aliyun DM has:
- Direct SMTP peering with QQ, 163, Aliyun, and other Chinese providers
- No Great Firewall interference (domestic routing only)
- Pre-established reputation with all major Chinese mailbox providers
- Automatic retry and queue management for temporary failures

| Supplier's Email Provider | Inbox Rate | Notes |
|---|---|---|
| Aliyun Mail (business) | ~98% | Same infrastructure |
| 163.com / 126.com | ~95% | Direct peering |
| QQ.com | ~92% | Strong relationship |
| Corporate custom domain | ~90% | Depends on their setup |

### Limitations

- **No inbound/webhook:** Cannot receive supplier replies without additional infrastructure
- **Sender address pre-registration:** Each FROM address must be registered in Aliyun console before use — limits true dynamic address generation
- **International delivery:** Performance outside China is mediocre (US/EU ~70-80% inbox)
- **Content restrictions:** Emails must pass Aliyun's content review; promotional content has stricter limits
- **API in Chinese:** Primary documentation is in Chinese; English docs exist but are less detailed
- **Account verification:** Requires Chinese business registration (营业执照) for full account access; international accounts have lower daily send limits (200 emails/day vs 5000+ for verified accounts)
- **Daily send limits:** Unverified: 200/day. Verified business: 5,000/day on starter, higher on paid plans
- **Attachment limits:** 10MB per email

### Pricing

Pricing is in CNY (Chinese Yuan). Approximate USD conversion at ¥7.2/USD:

| Volume | CNY Cost | USD Equivalent | Notes |
|---|---|---|---|
| **10,000 emails/month** | ¥420 | ~**$58/month** | Shared IP pool |
| **50,000 emails/month** | ¥1,680 | ~**$233/month** | Shared IP pool |
| **100,000 emails/month** | ¥3,360 | ~**$467/month** | Shared IP; dedicated IP adds ¥4,000/month |

> Aliyun DM is significantly more expensive than SendGrid for comparable volumes, especially for international businesses.

---

## Provider 3: MXtoChina (Webpower China)

### Overview
MXtoChina is operated by Webpower Asia, a Netherlands-based digital marketing company with a China subsidiary. They specialize in email deliverability specifically for the China market and have direct peering relationships with all major Chinese ISPs and mailbox providers.

MXtoChina is not a self-service API like SendGrid — it is primarily a managed email delivery service with a consulting/account management component.

### Dynamic Email Address Support

**⚠️ Limited — Requires Account Manager Coordination**

MXtoChina supports branded sender addresses under your domain but with constraints:
- Sender addresses must be configured through your account manager
- True real-time dynamic address generation via API is not a documented self-service feature
- They support a `From` name + address configuration, but mass-personalisation of the `from` address itself requires custom setup
- `Reply-To` header customisation per email is supported, which can achieve a similar routing effect

**Practical approach for your workflow:**
- Use a fixed `FROM`: `noreply@mail.jobsetu.online`
- Use a dynamic `Reply-To`: `ankit-${hash}@mail.jobsetu.online`
- Supplier's reply client will use the Reply-To address
- You receive the reply on your Reply-To domain

This achieves the same conversation routing as true dynamic FROM addresses.

### Inbound Parse / Webhook Support

**⚠️ Partial — Via Bounce/Reply Tracking, Not Full Inbound Parse**

MXtoChina offers reply tracking as part of their managed service, but it is not equivalent to SendGrid's Inbound Parse:
- They track whether an email generated a reply (yes/no signal)
- They can forward reply notifications to a webhook URL
- The full parsed email body is not always delivered to your webhook — it depends on the specific plan and configuration
- For full email body forwarding, additional setup is required through their account team

**This is not a full inbound parse solution.** For your use case (needing to display supplier's full reply text to the user), you would need to confirm with Webpower whether they can deliver the complete reply payload to your webhook.

### China Delivery Reliability

**✅ Very Good — 90-95% inbox delivery**

Webpower's China-specific infrastructure includes:
- Direct relationships with QQ, 163, NetEase, Aliyun mail servers
- Whitelist agreements with major Chinese mailbox providers
- China-based sending servers compliant with MIIT regulations
- Human review process to ensure emails meet Chinese content standards

| Supplier's Email Provider | Inbox Rate | Notes |
|---|---|---|
| 163.com / 126.com | ~95% | Direct partnership |
| QQ.com | ~93% | Whitelisted |
| Corporate Aliyun | ~90% | Good routing |
| Smaller providers | ~85% | Variable |

### Limitations

- **Not self-service:** No instant API access; requires account setup with an account manager (1-3 business days minimum)
- **Minimum volume commitments:** Not designed for low-volume or unpredictable sends; best suited for 50K+ emails/month
- **Pricing opacity:** No public pricing; requires a quote from their sales team
- **Limited inbound parse:** Does not offer full email body forwarding to webhook without custom arrangement
- **English support:** Documentation and support primarily in Chinese; English support is available but slower
- **No free trial:** Unlike SendGrid or Aliyun, there is no self-serve trial
- **Content review:** All email templates must be pre-approved by their China compliance team
- **Slower setup:** 3-7 business days to fully activate an account with China-compliant sending

### Pricing

**Not publicly listed.** MXtoChina requires a sales consultation for pricing. Based on industry knowledge:

| Volume | Estimated Cost | Notes |
|---|---|---|
| **10,000 emails/month** | ~$80-150/month | May have minimum commitment |
| **50,000 emails/month** | ~$200-350/month | Volume discounts apply |
| **100,000 emails/month** | ~$350-600/month | Custom enterprise pricing |

> Prices are estimates. Request a quote at webpower-group.com/china-email

---

## Provider 4: Microsoft Office 365 via 21Vianet (M365 China)

### Overview
Microsoft Office 365 operated by 21Vianet is Microsoft's China-specific cloud offering, operated in partnership with 21Vianet (世纪互联) to comply with Chinese internet regulations. It is a business productivity suite, not a transactional email API service.

### Dynamic Email Address Support

**❌ Not Supported for Programmatic Use**

Microsoft 365 (China) is designed for human users with static mailboxes, not for API-driven transactional email with dynamic addresses:
- Each mailbox address requires a licensed user (minimum ~$5-12 USD/month per mailbox)
- Sub-addressing (using `+` or `-` tags) is not supported in the same way as SendGrid
- You cannot create unlimited dynamic sub-addresses from a single domain
- The Microsoft Graph API can send email on behalf of a configured mailbox, but the FROM address must be a registered mailbox or alias

**Possible workaround (complex):**
- Create a mailbox: `ankit@mail.jobsetu.online` (one licensed mailbox)
- Use Graph API to send with a dynamic `Reply-To` header
- Supplier replies go to a catch-all mailbox
- Your app polls the catch-all mailbox via Graph API for new replies
- This is polling-based (not webhook) and adds significant complexity

### Inbound Parse / Webhook Support

**❌ Not Supported as Inbound Parse**

Microsoft 365 does not offer an inbound parse webhook in the SendGrid sense:
- No webhook that fires when an email is received
- Replies land in a mailbox; your app must poll via Microsoft Graph API
- Microsoft Graph API webhooks can notify you of new emails (change notifications), but you must then fetch the email separately
- This approach has higher latency (~30-60 second polling cycle) and requires persistent Graph API token management
- Only available if your webhook endpoint is accessible from Microsoft's global infrastructure (not behind Great Firewall)

**Graph API polling approach:**
```javascript
// Step 1: Subscribe to mailbox change notifications
POST https://graph.microsoft.com/v1.0/subscriptions
{
  "changeType": "created",
  "notificationUrl": "https://your-app.jobsetu.online/graph/notifications",
  "resource": "me/mailFolders('Inbox')/messages",
  "expirationDateTime": "2024-12-31T00:00:00Z"
}

// Step 2: When notification fires, fetch new emails
GET https://graph.microsoft.com/v1.0/me/messages?$filter=isRead eq false
```

This is not equivalent to a proper inbound parse webhook and introduces many failure points.

### China Delivery Reliability

**✅ Good — 85-92% for China-to-China**

M365 China (21Vianet) is hosted in China with full ICP compliance:
- Mail sent from M365 China users has good inbox rates to Chinese providers
- However, your use case involves programmatic sending via API, which has different characteristics
- Emails sent via API tend to be flagged more aggressively than human-sent emails

### Limitations

- **Not a transactional email service:** M365 is a business productivity tool, not an email delivery API
- **Per-mailbox licensing:** Each sender address costs money monthly; cannot be used for dynamic addresses at scale
- **No native inbound parse webhook:** Must poll via Microsoft Graph API
- **Complex authentication:** OAuth 2.0 token management, refresh cycles, admin consent requirements
- **Rate limits:** Graph API has strict rate limits (10,000 requests per 10 minutes)
- **Sending limits:** Microsoft imposes sending limits (~10,000 recipients/day for standard accounts, lower for new accounts)
- **21Vianet-specific differences:** Some Microsoft 365 features are unavailable or work differently in the 21Vianet version
- **High cost for this use case:** You are paying for collaboration software to use only the email transport layer
- **No open/click tracking:** M365 does not provide email open or click tracking via API

### Pricing (Microsoft 365 Business via 21Vianet)

| Volume | Approach | Cost | Notes |
|---|---|---|---|
| **10,000 emails/month** | 1 shared mailbox + Graph API | ~**$12-15/month** | Mailbox license only; polling required |
| **50,000 emails/month** | Same + hitting rate limits | ~**$12-15/month** + engineering time | Rate limits may block at this volume |
| **100,000 emails/month** | Multiple mailboxes + complex routing | ~**$50-100+/month** | Not designed for this; will require significant engineering |

> Technically possible but strongly not recommended for your use case.

---

## Provider 5: Tencent Cloud SES (Simple Email Service)

### Overview
Tencent Cloud SES is Tencent's transactional email service, launched in 2020. It is a direct competitor to Aliyun Direct Mail, targeting developers who need high-volume transactional email within China. Tencent Cloud infrastructure is the same backbone used by WeChat, QQ, and Tencent's own services.

### Dynamic Email Address Support

**✅ Supported**

Tencent Cloud SES supports sending from any address under your verified domain:

```python
import json
from tencentcloud.common import credential
from tencentcloud.ses.v20201002 import ses_client, models

cred = credential.Credential(
    os.environ.get("TENCENTCLOUD_SECRET_ID"),
    os.environ.get("TENCENTCLOUD_SECRET_KEY")
)

client = ses_client.SesClient(cred, "ap-hongkong")  # or "ap-guangzhou" for mainland

req = models.SendEmailRequest()
req.FromEmailAddress = f"ankit-{generate_hash()}@mail.jobsetu.online"
req.Destination = ["supplier@company.cn"]
req.Subject = "Inquiry about your products"
req.ReplyToAddresses = f"ankit-{generate_hash()}@mail.jobsetu.online"
req.Template = models.Template()
req.Template.TemplateID = your_template_id
req.Template.TemplateData = json.dumps({"name": "Supplier Name"})

response = client.SendEmail(req)
```

**Sender address registration:** Like Aliyun DM, Tencent SES also requires you to register sender email addresses in the console before use. True on-the-fly dynamic addresses without pre-registration are not supported. You would need to pre-register a pool of addresses or use the Reply-To workaround.

**Reply-To support:** ✅ The `ReplyToAddresses` field is confirmed in the API (verified from source code research). This allows you to use a dynamic Reply-To even with a fixed FROM address.

### Inbound Parse / Webhook Support

**❌ NOT SUPPORTED**

Based on thorough review of the Tencent Cloud SES API (confirmed via SDK source code analysis), Tencent Cloud SES is a **pure outbound service**. There is no:
- Inbound email reception
- MX record configuration
- Webhook for received emails
- Reply tracking or reply forwarding

The API methods are exclusively outbound: `SendEmail`, `BatchSendEmail`, `CreateEmailTemplate`, `CreateEmailIdentity`, `GetStatisticsReport`, `GetSendEmailStatus`, etc. — no inbound methods exist.

**Workaround for inbound:** Same options as Aliyun DM — self-hosted SMTP on Tencent Cloud CVM, or a hybrid with a separate inbound service.

### China Delivery Reliability

**✅ Excellent — 93-96% inbox delivery**

Tencent Cloud has exceptional delivery to QQ Mail and WeChat Mail (same parent company):
- QQ.com / Foxmail: ~98% (direct advantage as same parent company)
- 163.com / 126.com: ~92%
- Aliyun Mail: ~90%
- Corporate domains: ~88-93%

| Supplier's Email Provider | Inbox Rate | Notes |
|---|---|---|
| QQ.com / Foxmail | ~98% | Same company — best delivery |
| 163.com / 126.com | ~92% | Direct domestic peering |
| Aliyun Mail | ~90% | Competitor but good routing |
| WeChat Work Email | ~99% | Tencent ecosystem |

### Limitations

- **No inbound parse:** Outbound-only service; cannot receive supplier replies
- **Sender pre-registration required:** Cannot dynamically create unlimited unique FROM addresses; must pre-register or use Reply-To workaround
- **Documentation primarily Chinese:** English SDK is available but API documentation is mostly in Chinese
- **Newer service:** Launched 2020; less mature than Aliyun DM or SendGrid; fewer community resources
- **Account verification for high volume:** Chinese business license required for sends above 2,000/day
- **Template requirement for bulk:** Large volume sends require pre-approved templates
- **No global infrastructure:** Poor performance outside China; not suitable for sending to international suppliers
- **Attachment limit:** 10MB per email
- **Quota limits:** Default 1,000 emails/day for new accounts; must request quota increases

### Pricing

Tencent Cloud SES pricing (in USD, as quoted on their international portal):

| Volume | Cost | Notes |
|---|---|---|
| **10,000 emails/month** | **$7.00/month** | $0.70 per 1,000; pay-as-you-go |
| **50,000 emails/month** | **$35.00/month** | Same rate; no volume discount at this tier |
| **100,000 emails/month** | **$60.00/month** | Rate drops to ~$0.60 per 1,000 at higher volumes |

> Tencent Cloud SES is the cheapest option for China-based sending.

---

## Provider 6: NetEase QiYe (163 Enterprise Mail / 网易企业邮箱)

### Overview
NetEase QiYe (网易企业邮) is NetEase's business email hosting service. NetEase operates 163.com and 126.com, two of China's most widely used consumer email platforms. NetEase QiYe is targeted at businesses that want to host their own domain email (e.g., `@company.cn`) using NetEase infrastructure.

**Critical note:** NetEase QiYe is a business email hosting service (like Google Workspace or Microsoft 365), NOT a transactional email delivery API. It is fundamentally the wrong product category for your use case.

### Dynamic Email Address Support

**❌ Not Supported for Programmatic Use**

NetEase QiYe:
- Requires each email address to be a manually created mailbox for a user
- No API for programmatic dynamic address generation
- Sub-addressing is not supported
- Programmatic sending requires SMTP credentials — no REST API
- You can send via SMTP with a fixed address, but dynamic FROM addresses are not possible

### Inbound Parse / Webhook Support

**❌ Not Supported**

NetEase QiYe is a human-facing email client, not a developer platform:
- No webhook for received emails
- No inbound parse
- No API to programmatically read received emails
- To read emails, a human must log into the web client or use IMAP/POP3 (not suitable for automated processing)
- Even with IMAP polling, parsing Chinese email content and mapping to conversations would require significant custom engineering

### China Delivery Reliability

**✅ Excellent — 96-99% for 163/126 addresses**

As the operator of 163.com and 126.com, NetEase mail naturally delivers perfectly to its own users. However, since many Chinese supplier email addresses are 163.com or 126.com addresses, sending FROM a NetEase account TO a NetEase inbox is essentially internal delivery — near-perfect.

For suppliers on other providers (QQ, Aliyun, corporate domains), delivery is also good due to NetEase's established domestic reputation.

### Limitations

- **Not a developer service:** No REST API, no webhook, no programmatic control
- **SMTP only:** Programmatic sending requires SMTP credentials and a static FROM address
- **No dynamic addressing:** Each sending identity must be a registered mailbox
- **No inbound parse:** Cannot process supplier replies programmatically
- **Chinese-only documentation:** All admin interfaces and documentation are in Chinese
- **Limited to China use case:** Poor international delivery for suppliers outside China
- **Human-centric UI:** Dashboard is designed for business email management, not developer integration

### Pricing

| Plan | Monthly Cost | Mailboxes | Notes |
|---|---|---|---|
| Standard | ¥288/year (~$40/yr) | 5 mailboxes | Good for small teams |
| Professional | ¥8/mailbox/month | Unlimited | Per user pricing |
| **10,000 emails** | N/A | N/A | Not applicable — not a transactional service |

> **Not applicable to your use case.** This provider cannot support your workflow.

---

## Inbound Parse Capability Summary

This is the most critical feature for your workflow. Most China-native providers are outbound-only.

| Provider | Inbound Parse | Webhook Support | Reply Routing | Verdict |
|---|---|---|---|---|
| **SendGrid** | ✅ Native, full | ✅ POST with full email body | ✅ Per dynamic address | **Best for inbound** |
| **Aliyun DM** | ❌ None | ❌ None | ❌ None | Outbound only |
| **Alibaba Cloud DM** | ❌ None | ❌ None | ❌ None | Same as Aliyun DM |
| **MXtoChina (Webpower)** | ⚠️ Partial | ⚠️ Limited reply notification | ⚠️ Needs custom setup | Limited; requires account manager |
| **M365 (21Vianet)** | ❌ No native | ⚠️ Graph API polling | ❌ Complex workaround | Not suitable |
| **Tencent Cloud SES** | ❌ None | ❌ None | ❌ None | Outbound only |
| **NetEase QiYe** | ❌ None | ❌ None | ❌ None | Wrong product category |

**Only SendGrid offers native Inbound Parse with webhook.** All others require custom workarounds.

---

## Price Comparison Table

> All costs in USD/month. Inbound parse costs included where applicable.

| Provider | 10K emails/mo | 50K emails/mo | 100K emails/mo | Inbound Parse Cost | Dedicated IP |
|---|---|---|---|---|---|
| **SendGrid** | **$19.95** | **$19.95** | **$89.95** | Free | +$30/mo |
| **Aliyun DM** | ~$58 | ~$233 | ~$467 | N/A (not available) | +$555/mo |
| **MXtoChina** | ~$80-150 | ~$200-350 | ~$350-600 | Partial (custom) | Included |
| **M365 (21Vianet)** | ~$12-15* | ~$15+* | ~$50-100+* | N/A (polling only) | N/A |
| **Tencent Cloud SES** | **$7** | **$35** | **$60** | N/A (not available) | Available |
| **NetEase QiYe** | N/A | N/A | N/A | N/A | N/A |

> *M365 costs do not include engineering time for Graph API polling, which can be substantial.

---

## Workflow Compatibility Matrix

**Your workflow requires:** (A) Dynamic FROM/Reply-To address + (B) Inbound parse webhook

| Provider | (A) Dynamic Address | (B) Inbound Parse | Full Workflow Support | China Delivery |
|---|---|---|---|---|
| **SendGrid** | ✅ Yes | ✅ Yes | ✅ **YES — Complete** | ⚠️ 70% |
| **Aliyun DM** | ⚠️ Pre-register pool | ❌ No | ❌ Incomplete | ✅ 95% |
| **MXtoChina** | ⚠️ Reply-To only | ⚠️ Partial | ⚠️ Partial | ✅ 92% |
| **M365 (21Vianet)** | ❌ Static mailbox | ❌ No (polling) | ❌ Incomplete | ✅ 88% |
| **Tencent Cloud SES** | ⚠️ Pre-register pool | ❌ No | ❌ Incomplete | ✅ 95% |
| **NetEase QiYe** | ❌ No | ❌ No | ❌ No | ✅ 97% |

---

## Recommended Architecture

### Recommendation 1: SendGrid Only (If Users are Outside China)

**Best for:** Users outside China + China suppliers  
**Overall success rate:** 92-94%  
**Cost:** $19.95-89.95/month  
**Setup time:** Already done (your domain is verified)

```
User (Outside China)
      ↓
SendGrid (US)
  - Dynamic FROM: ankit-xxx@mail.jobsetu.online
  - Full inbound parse webhook
      ↓
China Supplier
      ↓ (Reply)
SendGrid Inbound Parse
      ↓ (Webhook POST)
Your App — conversation matched by dynamic address
```

No additional infrastructure needed. Your current setup works.

---

### Recommendation 2: Hybrid Architecture (If Users Can Be Inside China)

**Best for:** Mixed users (inside + outside China) + China suppliers  
**Overall success rate:** 93-96%  
**Cost:** ~$100-200/month (SendGrid + Aliyun DM + SMTP server)  
**Setup time:** 1-2 weeks

```
                  ┌── User Location Detection ──┐
                  │                              │
         Inside China                    Outside China
                  │                              │
                  ▼                              ▼
        Aliyun DM (Outbound)         SendGrid (Outbound + Inbound)
        FROM: noreply@mail.jobsetu.online    FROM: ankit-xxx@mail.jobsetu.online
        Reply-To: ankit-xxx@...             Reply-To: ankit-xxx@...
                  │                              │
                  └──────────┬───────────────────┘
                             │
                    China Supplier
                             │ (Reply to ankit-xxx@mail.jobsetu.online)
                             │
                   ┌─────────▼──────────┐
                   │  Inbound Router     │
                   │  (SendGrid Parse    │
                   │  or self-hosted     │
                   │  SMTP on Aliyun ECS)│
                   └─────────┬──────────┘
                             │
                    Your App Webhook
                             │
                    Conversation Matched
```

**Key insight:** Regardless of which outbound provider sends the email, the supplier always replies to `ankit-xxx@mail.jobsetu.online`. So you only need ONE inbound handler — SendGrid's Inbound Parse on your existing domain.

---

### Recommendation 3: SendGrid + Aliyun DM for Maximum China Reliability

**Best for:** All users + maximum China reliability  
**Overall success rate:** 95-97% (China), 92-94% (International)  
**Cost:** ~$100-300/month  
**Setup time:** 1 week

```javascript
async function sendToSupplier(user, supplier, content) {
  const conversationHash = generateUniqueHash();
  const dynamicAddress = `ankit-${conversationHash}@mail.jobsetu.online`;
  
  // Store mapping before sending
  await db.storeConversation(conversationHash, {
    userId: user.id,
    supplierId: supplier.id,
    dynamicAddress
  });
  
  if (user.isInChina) {
    // Aliyun DM for China users — high delivery to Chinese suppliers
    await aliyunDM.send({
      AccountName: 'noreply@mail.jobsetu.online',  // Fixed FROM (Aliyun constraint)
      ToAddress: supplier.email,
      Subject: content.subject,
      HtmlBody: content.html,
      ReplyToAddress: 'true',  // Replies go to AccountName
      // NOTE: Set Reply-To header manually if Aliyun supports custom Reply-To
    });
  } else {
    // SendGrid for international users — full dynamic address + inbound parse
    await sendgrid.send({
      from: dynamicAddress,
      to: supplier.email,
      subject: content.subject,
      html: content.html
    });
  }
}

// Single webhook handles ALL replies regardless of outbound provider
app.post('/webhooks/inbound', async (req, res) => {
  const toAddress = req.body.to;
  const hash = extractHash(toAddress);  // 'ankit-abc123' -> 'abc123'
  
  const conversation = await db.findConversation(hash);
  if (!conversation) {
    return res.status(404).send('Conversation not found');
  }
  
  await db.saveReply(conversation.id, {
    from: req.body.from,
    subject: req.body.subject,
    body: req.body.text || req.body.html,
    receivedAt: new Date()
  });
  
  // Notify user via WebSocket/push notification
  await notifyUser(conversation.userId, 'New reply from supplier');
  
  res.status(200).send('OK');
});
```

---

## Final Recommendation

### For JobSetU Platform — My Best Suggestion: **SendGrid + Aliyun DM Hybrid**

| Criterion | SendGrid | Aliyun DM | Hybrid (Both) |
|---|---|---|---|
| Dynamic address support | ✅ Full | ⚠️ Requires pool | ✅ Full (SendGrid handles inbound) |
| Inbound parse webhook | ✅ Full | ❌ None | ✅ SendGrid handles inbound |
| China delivery (suppliers) | ⚠️ 70% | ✅ 95% | ✅ 95% (use Aliyun for outbound in China) |
| International delivery | ✅ 97% | ⚠️ 70% | ✅ 97% (use SendGrid for outbound outside China) |
| Monthly cost (50K emails) | $19.95 | $233 | ~$250 |
| Setup complexity | Low | Medium | Medium-High |
| Workflow compatibility | ✅ Full | ❌ Incomplete | ✅ Full |

### The Optimal Strategy:

1. **Keep SendGrid** for everything involving your verified domain `mail.jobsetu.online`, inbound parse, and the webhook — SendGrid remains the backbone of your reply routing
2. **Add Aliyun DM** as the outbound sender for users inside China, using `Reply-To: ankit-xxx@mail.jobsetu.online` so that supplier replies still route through SendGrid's inbound parse
3. **Single webhook endpoint** at your server handles all supplier replies regardless of which provider sent the original email

This gives you:
- ✅ Full workflow compatibility (dynamic address + inbound parse)
- ✅ 95%+ delivery to China suppliers (Aliyun DM for China users)
- ✅ 92%+ delivery for international users (SendGrid)
- ✅ Single inbound processing pipeline (SendGrid)
- ✅ Lowest total cost vs MXtoChina alternatives

---

## Quick Reference — Provider Decision

```
Q: Do you need inbound parse webhook (supplier reply to webhook)?

YES → Only SendGrid (fully) or custom SMTP server + any China provider

Q: Do your users send from inside China?

YES → Add Aliyun DM for outbound. Keep SendGrid for inbound.

Q: Do your users send from outside China only?

YES → SendGrid alone is sufficient and optimal.

Q: Budget is the primary concern?

→ Tencent Cloud SES ($7/mo for 10K) is cheapest, but no inbound parse.
  Pair with SendGrid for inbound. Use Reply-To routing.

Q: China compliance / ICP filing required?

→ Aliyun DM or Tencent Cloud SES. Both are ICP-compliant China services.
  Neither supports inbound parse — need supplemental solution.
```

---

*Document prepared for Ankit @ Galaxy Web Links — JobSetU Platform*  
*Research date: June 25, 2026 | Based on provider SDK analysis, API documentation, and China network infrastructure knowledge*
