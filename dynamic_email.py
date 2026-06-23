"""FastAPI application for dynamic RFQ email management.

This module is the single entry point for the EmailPOC web server.  It wires
together three concerns:

1. **Email address generation** – each conversation gets a unique address of
   the form ``usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}`` that encodes the
   routing information directly in the local-part.

2. **Outbound email** – RFQ emails are sent via the SendGrid REST API, with
   the ``From`` and ``Reply-To`` headers both set to the dynamic address so
   that supplier replies are automatically routed back to the correct
   conversation.

3. **Inbound webhook** – SendGrid's Inbound Parse posts multipart form data
   to ``POST /webhooks/inbound`` for every email received at ``*@INBOUND_DOMAIN``.
   The handler parses the ``To`` address, persists the reply, and dispatches
   a lightweight classification action.

Configuration is read from environment variables (see ``.env``):

- ``SENDGRID_API_KEY`` *(required)* – SendGrid API key with Mail Send and
  Inbound Parse permissions.
- ``INBOUND_DOMAIN`` *(required)* – The domain whose MX records point to
  SendGrid's inbound parse servers, e.g. ``mail.yourdomain.com``.
- ``COMPANY_NAME`` *(optional)* – Display name used in outbound email
  signatures.  Defaults to ``"Your Company"``.

Run the server::

    uv run python main.py
    # or directly:
    uv run uvicorn dynamic_email:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import sendgrid
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sendgrid.helpers.mail import From, Mail, ReplyTo, To

from db import EmailDB

# ── Config ───────────────────────────────────────────────────────
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
INBOUND_DOMAIN   = os.getenv("INBOUND_DOMAIN")
COMPANY_NAME     = os.getenv("COMPANY_NAME")
FROM_EMAIL       = os.getenv("FROM_EMAIL")  # Must be a verified sender in SendGrid

sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
db = EmailDB()

# ── FastAPI app ───────────────────────────────────────────────────
Path("data/attachments").mkdir(parents=True, exist_ok=True)
Path("static").mkdir(exist_ok=True)

app = FastAPI(title="EmailPOC")
app.mount("/static",      StaticFiles(directory="static"),           name="static")
app.mount("/attachments", StaticFiles(directory="data/attachments"), name="attachments")

templates = Jinja2Templates(directory="templates")


# ── Email helpers ─────────────────────────────────────────────────

def generate_conversation_id() -> str:
    """Generate a short, unique 8-character hex conversation identifier.

    Uses the first 8 characters of a UUID4 (after stripping hyphens), giving
    roughly 4 billion unique values — sufficient for this POC.

    Returns:
        str: 8-character lowercase hexadecimal string, e.g. ``"3fa9c1b2"``.

    Example:
        >>> cid = generate_conversation_id()
        >>> len(cid)
        8
        >>> cid.isalnum()
        True
    """
    return str(uuid.uuid4()).replace("-", "")[:8]


def build_dynamic_email(user_id: str | int, conv_id: str) -> str:
    """Construct the dynamic email address for a conversation.

    The address encodes ``user_id`` and ``conv_id`` in the local-part so
    that both values can be recovered from any email that arrives at this
    address without requiring a database lookup on the MX side.

    Args:
        user_id (str | int): The platform user identifier.
        conv_id (str): The 8-character conversation identifier produced by
            :func:`generate_conversation_id`.

    Returns:
        str: Fully qualified email address, e.g.
            ``"usr42_conv3fa9c1b2@mail.yourdomain.com"``.

    Example:
        >>> build_dynamic_email(42, "3fa9c1b2")
        'usr42_conv3fa9c1b2@mail.yourdomain.com'
    """
    return f"usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}"


def parse_dynamic_email(email_address: str) -> dict | None:
    """Extract ``user_id`` and ``conv_id`` from a dynamic email address.

    Matches the pattern ``usr{user_id}_conv{conv_id}@{INBOUND_DOMAIN}``
    using a compiled regex.  The match is case-insensitive to handle
    upper-cased ``To`` headers from some email clients.

    Args:
        email_address (str): The raw ``To`` address from an inbound email,
            e.g. ``"usr42_conv3fa9c1b2@mail.yourdomain.com"``.

    Returns:
        dict | None: ``{"user_id": str, "conv_id": str}`` on success, or
            ``None`` if the address does not match the expected pattern.

    Example:
        >>> parse_dynamic_email("usr42_conv3fa9c1b2@mail.yourdomain.com")
        {'user_id': '42', 'conv_id': '3fa9c1b2'}

        >>> parse_dynamic_email("unknown@other.com") is None
        True
    """
    pattern = rf"usr(\w+)_conv([a-f0-9]{{8}})@{re.escape(INBOUND_DOMAIN)}"
    match = re.search(pattern, email_address, re.IGNORECASE)
    if match:
        return {"user_id": match.group(1), "conv_id": match.group(2)}
    return None


def create_conversation(
    user_id: str,
    supplier_email: str,
    supplier_name: str = "",
) -> dict:
    """Create and persist a new tracked conversation.

    Generates a unique conversation ID, builds the associated dynamic email
    address, stores the record via :class:`~db.EmailDB`, and returns the
    full conversation dict.

    Args:
        user_id (str): The platform user who owns this conversation.
        supplier_email (str): The supplier's email address that will receive
            the outbound RFQ.
        supplier_name (str): Human-readable display name for the supplier.
            Defaults to an empty string.

    Returns:
        dict: The newly created conversation record with keys:
            ``conv_id``, ``user_id``, ``supplier_email``, ``supplier_name``,
            ``email_address``, ``status`` (``"open"``), ``created_at``,
            ``reply_count`` (``0``), ``last_reply_at`` (``None``),
            ``emails_sent`` (``[]``), ``emails_received`` (``[]``).

    Example:
        >>> conv = create_conversation("42", "buyer@acme.com", "Acme Corp")
        >>> conv["status"]
        'open'
        >>> conv["email_address"]
        'usr42_conv3fa9c1b2@mail.yourdomain.com'
    """
    conv_id    = generate_conversation_id()
    email_addr = build_dynamic_email(user_id, conv_id)
    now        = datetime.now(timezone.utc).isoformat()

    conversation = {
        "conv_id":         conv_id,
        "user_id":         str(user_id),
        "supplier_email":  supplier_email,
        "supplier_name":   supplier_name,
        "email_address":   email_addr,
        "status":          "open",
        "created_at":      now,
        "reply_count":     0,
        "last_reply_at":   None,
        "emails_sent":     [],
        "emails_received": [],
    }
    db.insert_conversation(conversation)
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
    try:
        """Send an RFQ email via SendGrid from the conversation's dynamic address.

        Sets both ``From`` and ``Reply-To`` to the dynamic address so that all
        supplier replies are routed back through SendGrid Inbound Parse to
        ``POST /webhooks/inbound``.

        After a successful send the sent-email record is appended to the
        conversation in the DB and the product metadata is merged into the
        conversation root for display in the tracking UI.

        Args:
            user_id (str): The user who owns the conversation.
            conv_id (str): The 8-character conversation identifier.
            supplier_email (str): Destination address for the RFQ.
            supplier_name (str): Supplier display name used in the email salutation.
            product_name (str): Product being quoted, e.g. ``"Bluetooth Speaker X200"``.
            quantity (int): Number of units requested.
            target_price (str): Buyer's target unit price, e.g. ``"$12.00"``.

        Returns:
            dict: Result payload with keys:
                - ``status_code`` (int) – SendGrid HTTP status (202 = queued).
                - ``from`` (str) – The dynamic sender address.
                - ``to`` (str) – The supplier email address.
                - ``conv_id`` (str) – The conversation identifier.

        Raises:
            sendgrid.exceptions.UnauthorizedError: If the API key is invalid.
            Exception: Any other SendGrid or network error is propagated to the
                caller.

        Example:
            >>> result = send_rfq_email(
            ...     user_id="42",
            ...     conv_id="3fa9c1b2",
            ...     supplier_email="buyer@acme.com",
            ...     supplier_name="Acme Corp",
            ...     product_name="Speaker X200",
            ...     quantity=500,
            ...     target_price="$12.00",
            ... )
            >>> result["status_code"]
            202
        """
        dynamic_from = build_dynamic_email(user_id, conv_id)
        now          = datetime.now(timezone.utc).isoformat()
        subject_line = f"[RFQ-{conv_id[:4].upper()}] Request for Quotation — {product_name}"

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
            <strong>{COMPANY_NAME} Sourcing Team</strong></p>
            <hr style="border:none; border-top:1px solid #eee; margin-top:30px;">
            <p style="font-size:11px; color:#aaa;">
                Reference: CONV-{conv_id.upper()} | USR-{user_id}
            </p>
        </div>
        """
        # From must be a verified sender identity in SendGrid.
        # Reply-To is the dynamic address so supplier replies route back correctly.
        message = Mail(
            from_email   = From(FROM_EMAIL, COMPANY_NAME),
            to_emails    = To(supplier_email, supplier_name),
            subject      = subject_line,
            html_content = html_body,
        )
        message.reply_to = ReplyTo(dynamic_from)

        response = sg.send(message)

        sent_record = {
            "from_email":   FROM_EMAIL,
            "reply_to":     dynamic_from,
            "to_email":     supplier_email,
            "subject":      subject_line,
            "body_html":    html_body,
            "product_name": product_name,
            "quantity":     quantity,
            "target_price": target_price,
            "status_code":  response.status_code,
            "sent_at":      now,
        }
        db.add_sent_email(conv_id, sent_record)
        db.update_conversation(conv_id, {
            "product_name": product_name,
            "quantity":     quantity,
            "target_price": target_price,
            "subject":      subject_line,
        })

        return {
            "status_code": response.status_code,
            "from":        dynamic_from,
            "to":          supplier_email,
            "conv_id":     conv_id,
        }
    except Exception as e:
        raise e


# ── UI routes ─────────────────────────────────────────────────────

@app.get("/")
async def send_email_page(
    request: Request,
    success: str = "",
    error:   str = "",
    conv_id: str = "",
    user_id: str = "",
):
    """Render the Send RFQ form page.

    Displays the HTML form for composing and sending a new RFQ email.
    Optional query parameters allow the form to surface success or error
    feedback after a POST/redirect cycle.

    Args:
        request (Request): FastAPI request object (required by Jinja2).
        success (str): Non-empty value triggers a success banner with a link
            to the new conversation.
        error (str): Non-empty value triggers an error banner with the
            URL-decoded error message.
        conv_id (str): Conversation ID included in the success banner link.
        user_id (str): User ID included in the success banner link.

    Returns:
        TemplateResponse: Rendered ``index.html`` template.
    """
    return templates.TemplateResponse(request, "index.html", {
        "active_page": "send",
        "success":     success,
        "error":       error,
        "conv_id":     conv_id,
        "user_id":     user_id,
    })


@app.post("/send")
async def send_email_form(
    request:        Request,
    user_id:        str = Form(...),
    supplier_email: str = Form(...),
    supplier_name:  str = Form(...),
    product_name:   str = Form(...),
    quantity:       int = Form(...),
    target_price:   str = Form(...),
):
    """Process the RFQ form submission and send the email.

    Creates a new conversation, dispatches the RFQ via SendGrid, persists
    everything to the JSON store, then redirects to the conversation detail
    page on success.  Any exception is caught and the user is redirected back
    to the form with a URL-encoded error message.

    Args:
        request (Request): FastAPI request object.
        user_id (str): Platform user identifier submitted from the form.
        supplier_email (str): Supplier's email address.
        supplier_name (str): Supplier's display name.
        product_name (str): Name of the product being quoted.
        quantity (int): Requested quantity in units.
        target_price (str): Target unit price string, e.g. ``"$12.00"``.

    Returns:
        RedirectResponse: Redirects to ``/tracking/{user_id}/{conv_id}`` on
            success (HTTP 303), or back to ``/?error=…`` on failure.
    """
    try:
        conversation = create_conversation(user_id, supplier_email, supplier_name)
        conv_id = conversation["conv_id"]

        send_rfq_email(
            user_id=user_id,
            conv_id=conv_id,
            supplier_email=supplier_email,
            supplier_name=supplier_name,
            product_name=product_name,
            quantity=quantity,
            target_price=target_price,
        )

        return RedirectResponse(
            f"/tracking/{user_id}/{conv_id}?success=1",
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(
            f"/?error={quote(str(exc)[:300])}",
            status_code=303,
        )


@app.get("/tracking")
async def tracking_home(request: Request):
    """Render the Email Tracking home page with a user grid.

    Loads all user summaries and global statistics from the DB and renders
    them as a grid of clickable user cards.

    Args:
        request (Request): FastAPI request object.

    Returns:
        TemplateResponse: Rendered ``tracking.html`` with ``users`` (list of
            user summary dicts) and ``stats`` (aggregate counts dict).
    """
    users = db.get_all_users()
    stats = db.get_stats()
    return templates.TemplateResponse(request, "tracking.html", {
        "active_page": "tracking",
        "users":       users,
        "stats":       stats,
    })


@app.get("/tracking/{user_id}")
async def user_tracking(request: Request, user_id: str):
    """Render all conversations for a specific user.

    Fetches every conversation associated with ``user_id`` and displays them
    as a sortable table.  Clicking a row navigates to the conversation detail.

    Args:
        request (Request): FastAPI request object.
        user_id (str): The user whose conversations should be listed.

    Returns:
        TemplateResponse: Rendered ``user_conversations.html`` with
            ``user_id`` and ``conversations`` (list of conversation dicts,
            newest first).
    """
    conversations = db.get_user_conversations(user_id)
    return templates.TemplateResponse(request, "user_conversations.html", {
        "active_page":   "tracking",
        "user_id":       user_id,
        "conversations": conversations,
    })


@app.get("/tracking/{user_id}/{conv_id}")
async def conversation_detail(
    request: Request,
    user_id: str,
    conv_id: str,
    success: str = "",
):
    """Render the full email thread for a single conversation.

    Merges sent and received email records into a unified chronological
    timeline and passes it to the template.  Each item in the thread carries
    a ``direction`` key (``"sent"`` or ``"received"``) so the template can
    apply distinct visual styling.

    Args:
        request (Request): FastAPI request object.
        user_id (str): Owner of the conversation (used for auth check).
        conv_id (str): The 8-character conversation identifier.
        success (str): Non-empty triggers a success banner (used after a
            new RFQ is sent and the user is redirected here).

    Returns:
        TemplateResponse: Rendered ``conversation_detail.html`` with
            ``conversation`` (full record) and ``thread`` (sorted merged list).

    Raises:
        HTTPException: 404 if ``conv_id`` is not found or belongs to a
            different ``user_id``.
    """
    conversation = db.get_conversation(conv_id)
    if not conversation or str(conversation["user_id"]) != str(user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    thread = []
    for email in conversation.get("emails_sent", []):
        thread.append({**email, "direction": "sent",     "_ts": email.get("sent_at", "")})
    for email in conversation.get("emails_received", []):
        thread.append({**email, "direction": "received", "_ts": email.get("received_at", "")})
    thread.sort(key=lambda x: x.get("_ts", ""))

    return templates.TemplateResponse(request, "conversation_detail.html", {
        "active_page":  "tracking",
        "conversation": conversation,
        "thread":       thread,
        "success":      success,
    })


# ── Inbound webhook ───────────────────────────────────────────────

@app.post("/webhooks/inbound")
async def handle_inbound_email(request: Request):
    """Receive and process an inbound email posted by SendGrid Inbound Parse.

    SendGrid calls this endpoint (via the MX + webhook configuration) every
    time a message arrives at any ``*@{INBOUND_DOMAIN}`` address.  The
    handler performs the following steps in order:

    1. Parse the multipart form payload sent by SendGrid.
    2. Discard the message if its spam score exceeds 5.0.
    3. Extract ``user_id`` and ``conv_id`` from the ``To`` address using
       :func:`parse_dynamic_email`.  Log unmatched addresses for review.
    4. Save any binary attachments to ``data/attachments/`` and record their
       metadata.
    5. Persist the inbound record to the conversation via
       :meth:`~db.EmailDB.add_received_email`.
    6. Call :func:`_trigger_next_action` to classify the reply and optionally
       update the conversation status.

    Args:
        request (Request): FastAPI request object.  Body is read as
            multipart form data (``application/x-www-form-urlencoded`` or
            ``multipart/form-data`` depending on whether attachments exist).

    Returns:
        dict: One of three status payloads:
            - ``{"status": "skipped", "reason": "spam"}`` – spam score > 5.
            - ``{"status": "unmatched"}`` – ``To`` address not parseable.
            - ``{"status": "matched", "user_id": str, "conv_id": str}`` –
              reply successfully stored.
    """
    data = await request.form()

    from_email  = data.get("from", "")
    to_email    = data.get("to", "")
    subject     = data.get("subject", "")
    body_text   = data.get("text", "")
    body_html   = data.get("html", "")
    spam_score  = float(data.get("spam_score", "0") or "0")
    dkim_result = data.get("dkim", "")
    spf_result  = data.get("SPF", "")
    received_at = datetime.now(timezone.utc).isoformat()

    print(f"\n[Inbound] From: {from_email} → To: {to_email} | Subject: {subject}")

    if spam_score > 5.0:
        print(f"  Skipped — spam score {spam_score}")
        return {"status": "skipped", "reason": "spam"}

    parsed = parse_dynamic_email(to_email)
    if not parsed:
        db.insert_unmatched({
            "from_email":   from_email,
            "to_email":     to_email,
            "subject":      subject,
            "received_at":  received_at,
            "needs_review": True,
        })
        print(f"  Unmatched address: {to_email}")
        return {"status": "unmatched"}

    user_id = parsed["user_id"]
    conv_id = parsed["conv_id"]
    print(f"  Matched → user_id={user_id}, conv_id={conv_id}")

    # Handle attachments
    attachments: list[dict] = []
    num_attachments = int(data.get("attachments", 0) or 0)
    if num_attachments > 0:
        try:
            att_info = json.loads(data.get("attachment-info", "{}") or "{}")
        except Exception:
            att_info = {}

        for i in range(1, num_attachments + 1):
            att_file = data.get(f"attachment{i}")
            if att_file and hasattr(att_file, "read"):
                info      = att_info.get(f"attachment{i}", {})
                filename  = info.get("filename", f"attachment_{i}")
                ctype     = info.get("type", "application/octet-stream")
                content   = await att_file.read()
                safe_name = f"{conv_id}_{i}_{filename}"
                att_path  = f"data/attachments/{safe_name}"
                with open(att_path, "wb") as fh:
                    fh.write(content)
                attachments.append({
                    "filename":     filename,
                    "content_type": ctype,
                    "size":         len(content),
                    "url":          f"/attachments/{safe_name}",
                })

    inbound_record = {
        "from_email":   from_email,
        "to_email":     to_email,
        "subject":      subject,
        "body_text":    body_text,
        "body_html":    body_html,
        "attachments":  attachments,
        "dkim":         dkim_result,
        "spf":          spf_result,
        "spam_score":   str(spam_score),
        "received_at":  received_at,
    }
    db.add_received_email(conv_id, inbound_record)
    _trigger_next_action(user_id, conv_id, body_text, subject)

    return {"status": "matched", "user_id": user_id, "conv_id": conv_id}


def _trigger_next_action(
    user_id: str, conv_id: str, reply_body: str, subject: str
) -> None:
    """Classify a supplier reply and dispatch the appropriate next step.

    Uses simple keyword matching to bucket the reply into one of four action
    classes.  A ``DECLINED`` classification also marks the conversation status
    as ``"declined"`` in the DB.  This is the integration point for a
    LangGraph negotiation agent — see the commented-out ``agent.invoke`` block.

    Args:
        user_id (str): The user who owns the conversation.
        conv_id (str): The conversation receiving the reply.
        reply_body (str): Plain-text body of the inbound email.
        subject (str): Subject line of the inbound email.

    Returns:
        None

    Example:
        >>> _trigger_next_action("42", "3fa9c1b2", "Our price is $11.50/unit.", "RE: RFQ")
        # prints: Action: QUOTE_RECEIVED
    """
    rl = reply_body.lower()
    if any(w in rl for w in ["price", "quote", "usd", "$", "unit"]):
        action = "QUOTE_RECEIVED"
    elif any(w in rl for w in ["sorry", "cannot", "unable", "no stock"]):
        action = "DECLINED"
        db.update_conversation(conv_id, {"status": "declined"})
    elif any(w in rl for w in ["question", "clarif", "more info", "?"]):
        action = "CLARIFICATION_NEEDED"
    else:
        action = "MANUAL_REVIEW"

    print(f"  Action: {action}")
    # Hook your LangGraph agent here:
    # agent.invoke({"user_id": user_id, "conv_id": conv_id,
    #               "action": action, "reply_body": reply_body})
