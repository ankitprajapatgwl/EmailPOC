# ─────────────────────────────────────────────────────────────
# dynamic_email.py
# Full implementation: generate, send, receive, and track
# ─────────────────────────────────────────────────────────────
import os
import uuid
import re
import sendgrid
from sendgrid.helpers.mail import Mail, From, To, ReplyTo, Subject, HtmlContent
from fastapi import FastAPI, Request
from datetime import datetime

# ── Config ───────────────────────────────────────────────────
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
INBOUND_DOMAIN = "mail.yourdomain.com"
YOUR_COMPANY_NAME = "Your Company"

sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
app = FastAPI()


# ── PART 1: Generate Dynamic Address ─────────────────────────
def generate_conversation_id() -> str:
    """Generate a short unique conversation ID."""
    return str(uuid.uuid4()).replace("-", "")[:8]  # e.g. 3fa9c1b2


def build_dynamic_email(user_id: str | int, conv_id: str) -> str:
    """
    Build a dynamic email address encoding user_id + conv_id.

    Example:
        user_id = 42, conv_id = "3fa9c1b2"
        → usr42_conv3fa9c1b2@mail.yourdomain.com
    """
    return f"usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}"


def parse_dynamic_email(email_address: str) -> dict | None:
    """
    Extract user_id and conv_id from a dynamic email address.

    Input:  "usr42_conv3fa9c1b2@mail.yourdomain.com"
    Output: {"user_id": "42", "conv_id": "3fa9c1b2"}
    """
    pattern = rf"usr(\w+)_conv([a-f0-9]{{8}})@{re.escape(INBOUND_DOMAIN)}"
    match = re.search(pattern, email_address, re.IGNORECASE)
    if match:
        return {"user_id": match.group(1), "conv_id": match.group(2)}
    return None


# ── PART 2: Create Conversation + Send Email ─────────────────
def create_conversation(user_id: str, supplier_email: str) -> dict:
    """
    Create a new tracked conversation for a user + supplier.
    Returns the conversation record with its unique email address.
    """
    conv_id = generate_conversation_id()
    email_address = build_dynamic_email(user_id, conv_id)
    created_at = datetime.utcnow().isoformat()

    conversation = {
        "conv_id": conv_id,
        "user_id": user_id,
        "supplier_email": supplier_email,
        "email_address": email_address,
        "status": "open",
        "created_at": created_at,
        "reply_count": 0,
        "last_reply_at": None,
    }

    # Save to your database
    # db.conversations.insert(conversation)

    print(f"[Conversation Created]")
    print(f"  conv_id:       {conv_id}")
    print(f"  email_address: {email_address}")

    return conversation


def send_rfq_email(
    user_id: str,
    conv_id: str,
    supplier_email: str,
    supplier_name: str,
    product_name: str,
    quantity: int,
    target_price: str,
) -> dict:
    """
    Send an RFQ email FROM the dynamic address assigned to this conversation.
    All replies automatically route back to the same dynamic address.
    """
    dynamic_from = build_dynamic_email(user_id, conv_id)

    # Build HTML email body
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <p>Dear {supplier_name},</p>

        <p>I am writing to request a formal quotation for the following:</p>

        <table border="1" cellpadding="8" cellspacing="0"
               style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #f5f5f5;">
                <th>Product</th>
                <th>Quantity</th>
                <th>Target Price</th>
            </tr>
            <tr>
                <td>{product_name}</td>
                <td>{quantity} units</td>
                <td>{target_price} per unit</td>
            </tr>
        </table>

        <p>Please include the following in your quotation:</p>
        <ul>
            <li>Unit price at stated quantity (FOB)</li>
            <li>Minimum order quantity (MOQ)</li>
            <li>Lead time and production capacity</li>
            <li>Payment terms</li>
            <li>Product specifications and certifications</li>
        </ul>

        <p>We look forward to your response within 3 business days.</p>

        <p>Best regards,<br>
        <strong>{YOUR_COMPANY_NAME} Sourcing Team</strong></p>

        <hr style="border:none; border-top:1px solid #eee; margin-top:30px;">
        <p style="font-size:11px; color:#aaa;">
            Reference: CONV-{conv_id.upper()} | USR-{user_id}
        </p>
    </div>
    """

    # Build the SendGrid message
    message = Mail()
    message.from_email = From(dynamic_from, YOUR_COMPANY_NAME)
    message.to = To(supplier_email, supplier_name)
    message.reply_to = ReplyTo(dynamic_from)  # ← Replies come back here
    message.subject = Subject(
        f"[RFQ-{conv_id[:4].upper()}] Request for Quotation — {product_name}"
    )
    message.html_content = HtmlContent(html_body)

    # Send via SendGrid
    response = sg.send(message)

    result = {
        "status_code": response.status_code,  # 202 = success
        "from": dynamic_from,
        "to": supplier_email,
        "conv_id": conv_id,
    }

    print(f"[Email Sent] Status: {response.status_code}")
    print(f"  From: {dynamic_from}")
    print(f"  To:   {supplier_email}")

    return result


# ── PART 3: Receive + Track Inbound Replies ──────────────────


@app.post("/webhooks/inbound")
async def handle_inbound_email(request: Request):
    """
    SendGrid calls this endpoint when a supplier replies to any
    *@mail.yourdomain.com address.

    Flow:
    1. Extract To address from the POST data
    2. Parse user_id + conv_id from the To address
    3. Look up the conversation in DB
    4. Log the reply
    5. Trigger next agent action
    """
    data = await request.form()

    # ── Extract email fields ──────────────────────────────────
    from_email = data.get("from", "")
    to_email = data.get("to", "")
    subject = data.get("subject", "")
    body_text = data.get("text", "")
    body_html = data.get("html", "")
    spam_score = data.get("spam_score", "0")
    dkim_result = data.get("dkim", "")
    spf_result = data.get("SPF", "")
    received_at = datetime.utcnow().isoformat()

    print(f"\n[Inbound Email Received]")
    print(f"  From:    {from_email}")
    print(f"  To:      {to_email}")
    print(f"  Subject: {subject}")

    # ── Spam check ───────────────────────────────────────────
    if float(spam_score) > 5.0:
        print(f"  ⚠️  Spam score {spam_score} — skipping")
        return {"status": "skipped", "reason": "spam"}

    # ── Parse dynamic address ────────────────────────────────
    parsed = parse_dynamic_email(to_email)

    if not parsed:
        # Could not parse user_id + conv_id from To address
        print(f"  ❌ Could not parse dynamic address: {to_email}")

        # Log as unmatched for manual review
        unmatched = {
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "received_at": received_at,
            "needs_review": True,
        }
        # db.unmatched_emails.insert(unmatched)
        return {"status": "unmatched"}

    user_id = parsed["user_id"]
    conv_id = parsed["conv_id"]

    print(f"  ✅ Matched → user_id: {user_id}, conv_id: {conv_id}")

    # ── Look up conversation in DB ───────────────────────────
    # conversation = db.conversations.find_one({"conv_id": conv_id, "user_id": user_id})
    # if not conversation:
    #     return {"status": "conversation_not_found"}

    # ── Record the inbound reply ─────────────────────────────
    inbound_record = {
        "conv_id": conv_id,
        "user_id": user_id,
        "from_email": from_email,
        "to_email": to_email,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "dkim": dkim_result,
        "spf": spf_result,
        "spam_score": spam_score,
        "received_at": received_at,
    }
    # db.emails_received.insert(inbound_record)

    # ── Update conversation status ───────────────────────────
    # db.conversations.update(
    #     {"conv_id": conv_id},
    #     {"status": "replied", "last_reply_at": received_at,
    #      "$inc": {"reply_count": 1}}
    # )

    # ── Trigger next agent action ────────────────────────────
    trigger_next_action(user_id, conv_id, body_text, subject)

    return {"status": "matched", "user_id": user_id, "conv_id": conv_id}


def trigger_next_action(user_id: str, conv_id: str, reply_body: str, subject: str):
    """
    Decide what to do next based on the supplier's reply.
    This is where you hook in your LangGraph negotiation agent.
    """
    reply_lower = reply_body.lower()

    if any(word in reply_lower for word in ["price", "quote", "usd", "$", "unit"]):
        action = "QUOTE_RECEIVED"
        print(f"  🤖 Action: Quote received → trigger negotiation agent")

    elif any(word in reply_lower for word in ["sorry", "cannot", "unable", "no stock"]):
        action = "DECLINED"
        print(f"  🤖 Action: Supplier declined → try next supplier")

    elif any(word in reply_lower for word in ["question", "clarif", "more info", "?"]):
        action = "CLARIFICATION_NEEDED"
        print(f"  🤖 Action: Supplier has questions → auto-respond")

    else:
        action = "MANUAL_REVIEW"
        print(f"  🤖 Action: Unclassified reply → flag for user review")

    # Pass to your LangGraph agent
    # agent.invoke({
    #     "user_id":    user_id,
    #     "conv_id":    conv_id,
    #     "action":     action,
    #     "reply_body": reply_body
    # })
