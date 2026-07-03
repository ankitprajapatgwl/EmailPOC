"""HTTP routes for EmailPOC — UI pages and the single inbound webhook.

This module contains **only** route declarations. Every handler is thin: it
reads request input, delegates to the shared
:class:`~src.services.conversation_service.ConversationService` (and the
Jinja2 templates) stored on ``request.app.state``, and returns a response.
All construction and wiring lives in :mod:`src.app`, so this file can be
read as a flat table of "URL → behaviour".

Routes:

================ ====== ==============================================
Method + path           Purpose
================ ====== ==============================================
``GET /``               Render the Send RFQ form.
``POST /send``          Create a conversation and send the RFQ.
``GET /tracking``       User grid with aggregate stats.
``GET /tracking/{u}``   All conversations for one user.
``POST /tracking/{u}/delete`` Delete all of a user's conversations.
``GET /tracking/{u}/{c}`` Full conversation thread.
``POST /tracking/{u}/{c}/delete`` Delete a conversation.
``POST /webhooks/inbound`` Receive an inbound reply (any provider).
``GET /webhooks/inbound``  Validation probe (Elastic Email GETs this).
================ ====== ==============================================

Example:
    >>> from src.route import router
    >>> from fastapi import FastAPI
    >>> app = FastAPI()
    >>> app.include_router(router)            # doctest: +SKIP
"""

from typing import List
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse

from src.email_platform.email_master import EmailProviderError
from src.services.conversation_service import ConversationService

# A single router that :mod:`src.app` includes on the FastAPI application.
router = APIRouter()


# ── UI routes ────────────────────────────────────────────────────────

@router.get("/")
async def send_email_page(
    request: Request,
    success: str = "",
    error: str = "",
    conv_id: str = "",
    user_id: str = "",
):
    """Render the Send RFQ form page.

    Displays the HTML form for composing a new RFQ. Optional query
    parameters let the page surface success/error feedback after a
    POST/redirect cycle.

    Args:
        request (Request): FastAPI request (required by Jinja2).
        success (str): Non-empty value triggers a success banner.
        error (str): Non-empty value triggers an error banner with the
            URL-decoded message.
        conv_id (str): Conversation id used in the success banner link.
        user_id (str): User id used in the success banner link.

    Returns:
        TemplateResponse: The rendered ``index.html`` template.
    """
    templates = request.app.state.templates
    service: ConversationService = request.app.state.service
    return templates.TemplateResponse(request, "index.html", {
        "active_page": "send",
        "success": success,
        "error": error,
        "conv_id": conv_id,
        "user_id": user_id,
        "predefined_users": service.db.get_predefined_users(),
        "predefined_projects": service.db.get_predefined_projects(),
    })


@router.post("/send")
async def send_email_form(
    request: Request,
    user_id: str = Form(...),
    user_name: str = Form(...),
    project_id: str = Form(default=""),
    project_name: str = Form(default=""),
    supplier_email: str = Form(...),
    supplier_name: str = Form(...),
    product_name: str = Form(...),
    quantity: int = Form(...),
    target_price: str = Form(...),
    attachments: List[UploadFile] = File(default=[]),
):
    """Process the RFQ form submission and send the email.

    Creates a conversation, dispatches the RFQ through the active provider,
    persists everything and redirects to the conversation detail page on
    success. Provider/configuration failures are caught and surfaced to the
    user as a banner rather than a 500 page.

    Args:
        request (Request): FastAPI request.
        user_id (str): Platform user UUID from the dropdown selection.
        user_name (str): User's display name (hidden field, set by JS).
        supplier_email (str): Supplier's email address.
        supplier_name (str): Supplier's display name.
        product_name (str): Name of the product being quoted.
        quantity (int): Requested quantity in units.
        target_price (str): Target unit price string, e.g. ``"$12.00"``.

    Returns:
        RedirectResponse: ``303`` to ``/tracking/{user_id}/{conv_id}`` on
            success, or back to ``/?error=...`` on failure.
    """
    service: ConversationService = request.app.state.service
    log = request.app.state.log
    try:
        attachment_data = []
        for upload in attachments:
            if upload.filename:
                content = await upload.read()
                attachment_data.append({
                    "filename": upload.filename,
                    "content": content,
                    "content_type": (
                        upload.content_type or "application/octet-stream"
                    ),
                })

        conversation = service.create_conversation(
            user_id, user_name, supplier_email, supplier_name,
            project_id=project_id,
            project_name=project_name,
        )
        conv_id = conversation["conv_id"]

        service.send_rfq(
            user_id=user_id,
            conv_id=conv_id,
            supplier_email=supplier_email,
            supplier_name=supplier_name,
            product_name=product_name,
            quantity=quantity,
            target_price=target_price,
            attachments=attachment_data or None,
        )
        return RedirectResponse(
            f"/tracking/{user_id}/{conv_id}?success=1",
            status_code=303,
        )
    except EmailProviderError as exc:
        # Expected, well-described failure (bad key, send rejected, ...).
        log.error("Send failed: %s", exc)
        return RedirectResponse(
            f"/?error={quote(str(exc)[:300])}",
            status_code=303,
        )
    except Exception as exc:  # noqa: BLE001 - last-resort safety net
        log.exception("Unexpected error while sending RFQ")
        return RedirectResponse(
            f"/?error={quote(str(exc)[:300])}",
            status_code=303,
        )


@router.get("/tracking")
async def tracking_home(request: Request, deleted: str = ""):
    """Render the tracking home page with a user grid.

    Loads all user summaries and global statistics and renders them as a
    grid of clickable user cards.

    Args:
        request (Request): FastAPI request.
        deleted (str): Non-empty value triggers a "user deleted" banner
            after a delete/redirect cycle.

    Returns:
        TemplateResponse: Rendered ``tracking.html`` with ``users`` and
            ``stats``.
    """
    service: ConversationService = request.app.state.service
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "tracking.html", {
        "active_page": "tracking",
        "users": service.db.get_all_users(),
        "stats": service.db.get_stats(),
        "deleted": deleted,
    })


@router.post("/tracking/{user_id}/delete")
async def delete_user(request: Request, user_id: str):
    """Delete every conversation and email belonging to a user.

    This is the Email Tracking page's per-user delete action: it wipes
    all of the user's conversations, their sent/received emails and any
    attachment files, then redirects back to the user grid. It does not
    remove the user from the predefined users dropdown — they can still
    start new conversations afterwards.

    Args:
        request (Request): FastAPI request.
        user_id (str): The user whose tracking history should be wiped.

    Returns:
        RedirectResponse: ``303`` to ``/tracking?deleted=1``.
    """
    service: ConversationService = request.app.state.service
    service.delete_user_conversations(user_id)
    return RedirectResponse("/tracking?deleted=1", status_code=303)


@router.get("/tracking/{user_id}")
async def user_tracking(request: Request, user_id: str, deleted: str = ""):
    """Render all conversations for a specific user.

    Args:
        request (Request): FastAPI request.
        user_id (str): The user whose conversations should be listed.
        deleted (str): Non-empty value triggers a "conversation deleted"
            banner after a delete/redirect cycle.

    Returns:
        TemplateResponse: Rendered ``user_conversations.html`` with
            ``user_id`` and ``conversations`` (newest first).
    """
    service: ConversationService = request.app.state.service
    templates = request.app.state.templates
    conversations = service.db.get_user_conversations(user_id)
    user_info = service.db.get_user_by_id(user_id) or {}
    return templates.TemplateResponse(
        request,
        "user_conversations.html",
        {
            "active_page": "tracking",
            "user_id": user_id,
            "user_name": user_info.get("full_name") or f"User {user_id[:8]}",
            "user_email": user_info.get("email", ""),
            "conversations": conversations,
            "deleted": deleted,
        },
    )


@router.get("/tracking/{user_id}/{conv_id}")
async def conversation_detail(
    request: Request,
    user_id: str,
    conv_id: str,
    success: str = "",
):
    """Render the full email thread for a single conversation.

    Merges sent and received records into one chronological timeline; each
    item carries a ``direction`` key so the template can style sent vs
    received differently.

    Args:
        request (Request): FastAPI request.
        user_id (str): Owner of the conversation (used for the auth check).
        conv_id (str): The 8-character conversation identifier.
        success (str): Non-empty triggers a success banner.

    Returns:
        TemplateResponse: Rendered ``conversation_detail.html`` with
            ``conversation`` and ``thread``.

    Raises:
        HTTPException: ``404`` if ``conv_id`` is not found or belongs to a
            different ``user_id``.
    """
    service: ConversationService = request.app.state.service
    templates = request.app.state.templates

    conversation = service.db.get_conversation(conv_id)
    if not conversation or str(conversation["user_id"]) != str(user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    thread = []
    for email in conversation.get("emails_sent", []):
        thread.append({
            **email,
            "direction": "sent",
            "_ts": email.get("sent_at", ""),
        })
    for email in conversation.get("emails_received", []):
        thread.append({
            **email,
            "direction": "received",
            "_ts": email.get("received_at", ""),
        })
    thread.sort(key=lambda item: item.get("_ts", ""))

    return templates.TemplateResponse(
        request,
        "conversation_detail.html",
        {
            "active_page": "tracking",
            "conversation": conversation,
            "thread": thread,
            "success": success,
        },
    )


@router.post("/tracking/{user_id}/{conv_id}/delete")
async def delete_conversation(request: Request, user_id: str, conv_id: str):
    """Delete a conversation and its attachments, then redirect.

    Args:
        request (Request): FastAPI request.
        user_id (str): Owner of the conversation (used for the auth check).
        conv_id (str): The 8-character conversation identifier to delete.

    Returns:
        RedirectResponse: ``303`` to ``/tracking/{user_id}?deleted=1``.

    Raises:
        HTTPException: ``404`` if ``conv_id`` is not found or belongs to a
            different ``user_id``.
    """
    service: ConversationService = request.app.state.service
    if not service.delete_conversation(conv_id, user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return RedirectResponse(f"/tracking/{user_id}?deleted=1", status_code=303)


# ── Inbound webhook (single URL for every provider) ──────────────────

@router.post("/webhooks/inbound")
async def handle_inbound_email(request: Request):
    """Receive and process one inbound email from any provider.

    This is the single endpoint every provider's inbound feature posts to.
    The provider-specific parsing, conversation matching, attachment
    storage and reply classification all happen inside
    :meth:`ConversationService.handle_inbound`; the active provider is
    chosen once at startup from ``EMAIL_PROVIDER``.

    Args:
        request (Request): FastAPI request. The body is form or JSON data
            depending on the provider.

    Returns:
        dict: A status payload describing the outcome — one of ``matched``,
            ``unmatched``, ``skipped`` (spam), ``rejected`` (bad signature)
            or ``error``.
    """
    service: ConversationService = request.app.state.service
    return await service.handle_inbound(request)


@router.get("/webhooks/inbound")
async def validate_inbound_webhook():
    """Answer the GET probe some providers send before saving a route.

    Elastic Email (and others) validate an inbound notification URL by
    issuing a ``GET`` and requiring a ``2xx`` response before they will save
    it. This handler exists solely to satisfy that probe.

    Returns:
        dict: ``{"status": "ok"}`` with an implicit ``200`` status.
    """
    return {"status": "ok"}
