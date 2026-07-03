"""Conversation orchestration for EmailPOC.

:class:`ConversationService` is the single place that coordinates the
database, the active email provider and the active inbound webhook parser.
It exposes three high-level operations the routes call:

1. :meth:`ConversationService.create_conversation` – mint a conversation
   and its dynamic address.
2. :meth:`ConversationService.send_rfq` – render and send the RFQ email,
   then persist the sent record.
3. :meth:`ConversationService.handle_inbound` – parse an inbound webhook
   request, match it to a conversation, store attachments and the reply,
   and classify the supplier's response.

Keeping this logic out of the routes means the same flow works unchanged no
matter which provider is configured.

Example:
    >>> service = ConversationService(           # doctest: +SKIP
    ...     db, email_provider, webhook_parser, settings, logger)
    >>> conv = service.create_conversation("42", "buyer@acme.com", "Acme")
    >>> conv["status"]                            # doctest: +SKIP
    'open'
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request

from src.config import Settings
from src.db import EmailDB
from src.email_platform.email_master import EmailMaster
from src.webhook_factory.webhook_master import (
    InboundEmail,
    WebhookParseError,
    WebhookParserMaster,
)

# Inbound emails scoring above this SpamAssassin-style threshold are
# discarded before being matched to a conversation.
_SPAM_THRESHOLD = 5.0


class ConversationService:
    """Coordinate conversations, outbound sends and inbound replies.

    Attributes:
        db (EmailDB): The JSON persistence layer.
        email (EmailMaster): The active outbound email provider. Its
            inherited address helpers are reused on the inbound side so the
            encode/decode logic has a single source of truth.
        webhook (WebhookParserMaster): The active inbound webhook parser.
        settings (Settings): Shared application configuration.
        log (logging.Logger): Shared application logger.

    Example:
        >>> service = ConversationService(       # doctest: +SKIP
        ...     db, email_provider, webhook_parser, settings, logger)
    """

    def __init__(
        self,
        db: EmailDB,
        email_provider: EmailMaster,
        webhook_parser: WebhookParserMaster,
        settings: Settings,
        logger: logging.Logger,
    ) -> None:
        """Store the collaborators this service orchestrates.

        Args:
            db (EmailDB): The JSON persistence layer.
            email_provider (EmailMaster): The active outbound provider.
            webhook_parser (WebhookParserMaster): The active inbound parser.
            settings (Settings): Shared application configuration.
            logger (logging.Logger): Shared application logger.

        Returns:
            None
        """
        self.db = db
        self.email = email_provider
        self.webhook = webhook_parser
        self.settings = settings
        self.log = logger

    # ── Outbound ─────────────────────────────────────────────────────

    def create_conversation(
        self,
        user_id: str,
        user_name: str,
        supplier_email: str,
        supplier_name: str = "",
        project_id: str = "",
        project_name: str = "",
    ) -> dict:
        """Create and persist a new tracked conversation.

        Generates a unique thread_id (used as conv_id for email routing),
        builds the associated dynamic email address, stores the record in
        ``conversations``, ``user_conversations``, and ``threads`` tables.

        Args:
            user_id (str): The platform user UUID who owns this conversation.
            user_name (str): The user's display name.
            supplier_email (str): The supplier address for the outbound RFQ.
            supplier_name (str): Human-readable supplier display name.
            project_id (str): UUID of the selected predefined project.
                When provided this is stored as the "Conversation ID" for
                grouping; the generated thread_id handles email routing.
            project_name (str): Product name from the selected project.

        Returns:
            dict: The newly created conversation record.
        """
        thread_id = self.email.generate_conversation_id()
        # conv_id = thread_id for email routing; project_id is the business
        # level conversation identifier displayed in the UI.
        conv_id = thread_id
        email_addr = self.email.build_dynamic_email(user_name, conv_id)
        now = datetime.now(timezone.utc).isoformat()

        conversation = {
            "conv_id": conv_id,
            "thread_id": thread_id,
            "project_id": project_id,
            "project_name": project_name,
            "user_id": str(user_id),
            "user_name": user_name,
            "supplier_email": supplier_email,
            "supplier_name": supplier_name,
            "email_address": email_addr,
            "provider": self.email.provider_name,
            "status": "open",
            "created_at": now,
            "reply_count": 0,
            "last_reply_at": None,
            "emails_sent": [],
            "emails_received": [],
        }
        self.db.insert_conversation(conversation)

        user_info = self.db.get_user_by_id(user_id)
        self.db.insert_user_conversation(
            conv_id=conv_id,
            user_id=str(user_id),
            user_name=user_name,
            user_email=user_info.get("email", "") if user_info else "",
            created_at=now,
        )

        self.db.insert_thread(
            thread_id=thread_id,
            conv_id=conv_id,
            project_id=project_id,
            project_name=project_name,
            user_id=str(user_id),
            user_name=user_name,
            created_at=now,
        )

        self.log.info(
            "Created conversation %s (thread=%s project=%s user=%s provider=%s)",
            conv_id,
            thread_id,
            project_id or "none",
            user_id,
            self.email.provider_name,
        )
        return conversation

    def send_rfq(
        self,
        *,
        user_id: str,
        conv_id: str,
        supplier_email: str,
        supplier_name: str,
        product_name: str,
        quantity: int,
        target_price: str,
        attachments: list | None = None,
    ) -> dict:
        """Render and send an RFQ email, then persist the sent record.

        The ``From`` header is the verified sender (``FROM_EMAIL``); the
        ``Reply-To`` header is the conversation's dynamic address so that
        replies route back to the inbound webhook. After a successful send
        the record is appended to the conversation and the product metadata
        is merged into the conversation root for the tracking UI.

        Args:
            user_id (str): The user who owns the conversation.
            conv_id (str): The 8-character conversation identifier.
            supplier_email (str): Destination address for the RFQ.
            supplier_name (str): Supplier display name for the salutation.
            product_name (str): Product being quoted.
            quantity (int): Number of units requested.
            target_price (str): Buyer's target unit price, e.g. ``"$12.00"``.

        Returns:
            dict: Summary with keys ``status_code``, ``provider``, ``from``,
                ``to`` and ``conv_id``.

        Raises:
            EmailProviderError: If the provider is misconfigured or the send
                fails (subclasses :class:`ProviderConfigError` and
                :class:`EmailSendError`).

        Example:
            >>> result = service.send_rfq(            # doctest: +SKIP
            ...     user_id="42", conv_id="3fa9c1b2",
            ...     supplier_email="buyer@acme.com",
            ...     supplier_name="Acme", product_name="X200",
            ...     quantity=500, target_price="$12.00")
            >>> result["status_code"]                 # doctest: +SKIP
            202
        """
        conversation = self.db.get_conversation(conv_id)
        reply_to = (
            conversation["email_address"]
            if conversation
            else self.email.build_dynamic_email(user_id, conv_id)
        )
        subject = self.email.build_rfq_subject(conv_id, product_name)
        html_body = self.email.build_rfq_html(
            user_id=user_id,
            conv_id=conv_id,
            supplier_name=supplier_name,
            product_name=product_name,
            quantity=quantity,
            target_price=target_price,
        )
        now = datetime.now(timezone.utc).isoformat()

        # Delegate transmission to the active provider. Any failure raises
        # an EmailProviderError, which the route turns into a user message
        # self.settings.from_email,
        result = self.email.send_email(
            from_email=reply_to,
            from_name=self.settings.company_name,
            to_email=supplier_email,
            to_name=supplier_name,
            subject=subject,
            html_body=html_body,
            reply_to=reply_to,
            attachments=attachments,
        )

        sent_record = {
            "email_type": "new_thread",
            "from_email": reply_to,
            "reply_to": reply_to,
            "to_email": supplier_email,
            "subject": subject,
            "body_html": html_body,
            "product_name": product_name,
            "quantity": quantity,
            "target_price": target_price,
            "attachments": [
                {"filename": a["filename"],
                 "content_type": a.get("content_type", "application/octet-stream"),
                 "size": len(a["content"])}
                for a in (attachments or [])
            ],
            "provider": result.get("provider"),
            "provider_message_id": result.get("provider_message_id"),
            "status_code": result.get("status_code"),
            "sent_at": now,
        }
        self.db.add_sent_email(conv_id, sent_record)
        self.db.update_conversation(conv_id, {
            "product_name": product_name,
            "quantity": quantity,
            "target_price": target_price,
            "subject": subject,
        })

        return {
            "status_code": result.get("status_code"),
            "provider": result.get("provider"),
            "from": reply_to,
            "to": supplier_email,
            "conv_id": conv_id,
        }

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        """Delete a conversation owned by ``user_id`` and its attachments.

        Verifies ownership before deleting anything, so one user cannot
        delete another user's conversation by guessing its id. Attachment
        files are named ``{conv_id}_...`` on disk (see
        :meth:`~src.webhook_factory.webhook_master.WebhookParserMaster.persist_attachments`),
        so they can be removed with a simple glob.

        Args:
            conv_id (str): The conversation to delete.
            user_id (str): The user requesting the deletion.

        Returns:
            bool: True if the conversation existed and belonged to
                ``user_id`` and was deleted, False otherwise.
        """
        conversation = self.db.get_conversation(conv_id)
        if not conversation or str(conversation["user_id"]) != str(user_id):
            return False

        for path in Path(self.settings.attachments_dir).glob(f"{conv_id}_*"):
            path.unlink(missing_ok=True)

        self.db.delete_conversation(conv_id, user_id)
        self.log.info("Deleted conversation %s for user %s", conv_id, user_id)
        return True

    def delete_user_conversations(self, user_id: str) -> int:
        """Delete every conversation, email and attachment for a user.

        Used by the Email Tracking page's per-user delete action, where
        deleting a user is really "wipe all conversations owned by this
        user" — the underlying ``EmailDB`` has no separate user record to
        remove, and the fixed ``predefined_users`` dropdown list is left
        untouched so the user can still start new conversations later.

        Args:
            user_id (str): The user whose entire tracking history should
                be wiped.

        Returns:
            int: The number of conversations deleted.
        """
        conv_ids = self.db.delete_user_conversations(user_id)
        for conv_id in conv_ids:
            for path in Path(self.settings.attachments_dir).glob(f"{conv_id}_*"):
                path.unlink(missing_ok=True)
        self.log.info(
            "Deleted %d conversation(s) and their attachments for user %s",
            len(conv_ids),
            user_id,
        )
        return len(conv_ids)

    # ── Inbound ──────────────────────────────────────────────────────

    async def handle_inbound(self, request: Request) -> dict:
        """Parse and process one inbound webhook request end-to-end.

        Pipeline:

        1. Parse the provider payload into an :class:`InboundEmail`.
        2. Reject it if the signature could not be verified.
        3. Skip it if the spam score exceeds the threshold.
        4. Decode the ``To`` address into ``user_id`` / ``conv_id``; record
           it for manual review if it does not match the dynamic pattern.
        5. Persist any attachments and the reply, then classify it.

        Args:
            request (Request): The FastAPI request for the inbound POST.

        Returns:
            dict: A status payload — one of
                ``{"status": "error"}``,
                ``{"status": "rejected", "reason": "invalid_signature"}``,
                ``{"status": "skipped", "reason": "spam"}``,
                ``{"status": "unmatched"}`` or
                ``{"status": "matched", "user_id": ..., "conv_id": ...,
                "action": ...}``.

        Example:
            >>> payload = await service.handle_inbound(req)  # noqa
            >>> payload["status"]                            # doctest: +SKIP
            'matched'
        """
        try:
            inbound = await self.webhook.parse(request)
        except WebhookParseError as exc:
            self.log.error("Inbound parse failed: %s", exc)
            return {"status": "error", "reason": str(exc)}

        self.log.info(
            "[Inbound] %s -> %s | %s",
            inbound.from_email,
            inbound.to_email,
            inbound.subject,
        )

        if not inbound.signature_verified:
            self.log.warning("Rejected inbound: signature not verified")
            return {"status": "rejected", "reason": "invalid_signature"}

        if inbound.spam_score > _SPAM_THRESHOLD:
            self.log.info(
                "Skipped inbound: spam score %s", inbound.spam_score
            )
            return {"status": "skipped", "reason": "spam"}

        return self._record_inbound(inbound)

    def _record_inbound(self, inbound: InboundEmail) -> dict:
        """Match a parsed inbound email and persist it.

        Args:
            inbound (InboundEmail): The normalised inbound email.

        Returns:
            dict: ``{"status": "unmatched"}`` if the ``To`` address does not
                decode, otherwise
                ``{"status": "matched", "user_id": ..., "conv_id": ...,
                "action": ...}``.
        """
        received_at = datetime.now(timezone.utc).isoformat()
        parsed = self.email.parse_dynamic_email(inbound.to_email)

        if not parsed:
            self.db.insert_unmatched({
                "from_email": inbound.from_email,
                "to_email": inbound.to_email,
                "subject": inbound.subject,
                "provider": inbound.provider,
                "received_at": received_at,
                "needs_review": True,
            })
            self.log.info("Unmatched inbound address: %s", inbound.to_email)
            return {"status": "unmatched"}

        conv_id = parsed["conv_id"]
        conversation = self.db.get_conversation(conv_id)
        if not conversation:
            self.db.insert_unmatched({
                "from_email": inbound.from_email,
                "to_email": inbound.to_email,
                "subject": inbound.subject,
                "provider": inbound.provider,
                "received_at": received_at,
                "needs_review": True,
            })
            self.log.info("Unmatched conv_id %s in address: %s", conv_id, inbound.to_email)
            return {"status": "unmatched"}

        user_id = conversation["user_id"]
        self.log.info("Matched inbound -> user=%s conv=%s", user_id, conv_id)

        attachments = self.webhook.persist_attachments(
            conv_id, inbound.attachments
        )
        inbound_record = {
            "email_type": self._detect_email_type(inbound.subject),
            "from_email": inbound.from_email,
            "to_email": inbound.to_email,
            "subject": inbound.subject,
            "body_text": inbound.body_text,
            "body_html": inbound.body_html,
            "attachments": attachments,
            "dkim": inbound.dkim,
            "spf": inbound.spf,
            "spam_score": str(inbound.spam_score),
            "provider": inbound.provider,
            "received_at": received_at,
        }
        self.db.add_received_email(conv_id, inbound_record)
        action = self._classify_reply(conv_id, inbound.body_text)

        return {
            "status": "matched",
            "user_id": user_id,
            "conv_id": conv_id,
            "action": action,
        }

    def _classify_reply(self, conv_id: str, reply_body: str) -> str:
        """Classify a supplier reply with simple keyword matching.

        Buckets the reply into one of four action classes. A ``DECLINED``
        classification also flips the conversation status to ``"declined"``.
        This is the integration point for a future negotiation agent.

        Args:
            conv_id (str): The conversation receiving the reply.
            reply_body (str): Plain-text body of the inbound email.

        Returns:
            str: One of ``"QUOTE_RECEIVED"``, ``"DECLINED"``,
                ``"CLARIFICATION_NEEDED"`` or ``"MANUAL_REVIEW"``.

        Example:
            >>> service._classify_reply(             # doctest: +SKIP
            ...     "3fa9c1b2", "Our price is $11.50/unit.")
            'QUOTE_RECEIVED'
        """
        text = (reply_body or "").lower()
        if any(w in text for w in ["price", "quote", "usd", "$", "unit"]):
            action = "QUOTE_RECEIVED"
        elif any(
            w in text for w in ["sorry", "cannot", "unable", "no stock"]
        ):
            action = "DECLINED"
            self.db.update_conversation(conv_id, {"status": "declined"})
        elif any(
            w in text for w in ["question", "clarif", "more info", "?"]
        ):
            action = "CLARIFICATION_NEEDED"
        else:
            action = "MANUAL_REVIEW"

        self.log.info("Reply on %s classified as %s", conv_id, action)
        # Hook a negotiation agent here, e.g.:
        #   agent.invoke({"conv_id": conv_id, "action": action, ...})
        return action

    @staticmethod
    def _detect_email_type(subject: str) -> str:
        """Detect whether an inbound email is a reply, forward, or new thread.

        Args:
            subject (str): The subject line of the inbound email.

        Returns:
            str: One of ``"reply"``, ``"forwarded"``, or ``"new_thread"``.
        """
        s = (subject or "").strip().lower()
        if s.startswith("re:") or s.startswith("re "):
            return "reply"
        if s.startswith("fwd:") or s.startswith("fw:") or s.startswith("fwd "):
            return "forwarded"
        return "new_thread"
