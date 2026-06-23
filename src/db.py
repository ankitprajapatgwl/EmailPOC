"""JSON-backed persistence layer for EmailPOC conversations and emails.

This module provides a single class, :class:`EmailDB`, that serialises all
application state to a JSON file on disk. A :class:`threading.Lock` guards
every write so the class is safe to use from multiple concurrent FastAPI
request handlers in the same process.

Data is stored under three top-level keys:

- ``conversations`` – dict keyed by ``conv_id``; each value is a full
  conversation record including its sent and received email lists.
- ``users`` – dict keyed by ``user_id``; each value is a list of
  ``conv_id`` strings belonging to that user.
- ``unmatched_emails`` – list of inbound payloads whose ``To`` address
  could not be parsed into a ``(user_id, conv_id)`` pair.

The store is provider-agnostic: the same schema is used no matter which
email provider (SendGrid, Mailgun or Elastic Email) produced the records.

Example:
    >>> from src.db import EmailDB
    >>> db = EmailDB("data/db.json")
    >>> db.insert_conversation({"conv_id": "abc12345", "user_id": "42"})
    >>> db.get_conversation("abc12345")["user_id"]
    '42'
"""

import json
import logging
from pathlib import Path
from threading import Lock

from src.logger import AppLogger


class EmailDB:
    """Thread-safe JSON file store for conversation and email data.

    All public write methods acquire a process-wide lock before loading the
    JSON file, mutating the in-memory dict and flushing it back to disk.
    Read-only methods do not acquire the lock, so they may observe slightly
    stale data under heavy concurrent writes — acceptable for this POC.

    Attributes:
        db_path (str): Filesystem path to the backing JSON file.
        log (logging.Logger): Shared application logger used for debug and
            error reporting.

    Example:
        >>> db = EmailDB("data/test.json")
        >>> db.insert_conversation({"conv_id": "abc12345", "user_id": "42"})
        >>> db.get_conversation("abc12345")["conv_id"]
        'abc12345'
    """

    def __init__(
        self,
        db_path: str = "data/db.json",
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialise the store, creating the JSON file if it is missing.

        Creates all parent directories for ``db_path`` automatically. If the
        file is absent a fresh store with empty collections is written to
        disk so subsequent reads never have to handle a missing-file error.

        Args:
            db_path (str): Path to the JSON file used as the store. Defaults
                to ``"data/db.json"`` relative to the working directory.
            logger (logging.Logger | None): Shared application logger. When
                ``None`` the global shared logger is fetched instead, so the
                store always has somewhere to report.

        Returns:
            None

        Example:
            >>> db = EmailDB()                       # uses data/db.json
            >>> db = EmailDB("tmp/test_store.json")  # custom path for tests
        """
        self.db_path = str(db_path)
        self.log = logger or AppLogger.get()
        self._lock = Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if not Path(self.db_path).exists():
            self.log.info("Creating new JSON store at %s", self.db_path)
            self._write({
                "conversations": {},
                "users": {},
                "unmatched_emails": [],
            })

    # ── Internal helpers ─────────────────────────────────────────────

    def _read(self) -> dict:
        """Load and return the entire store from disk.

        Reads the JSON file on every call — there is no in-memory caching —
        so the returned dict always reflects the most recently persisted
        state.

        Returns:
            dict: The full store dict with keys ``conversations``,
                ``users`` and ``unmatched_emails``.
        """
        with open(self.db_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, data: dict) -> None:
        """Serialise ``data`` and overwrite the store file.

        Uses ``json.dump`` with ``default=str`` so non-serialisable values
        (such as :class:`datetime.datetime` objects) are coerced to strings
        rather than raising a :class:`TypeError`.

        Args:
            data (dict): The full store dict to persist.

        Returns:
            None
        """
        with open(self.db_path, "w", encoding="utf-8") as handle:
            json.dump(
                data, handle, indent=2, default=str, ensure_ascii=False
            )

    # ── Write methods ────────────────────────────────────────────────

    def insert_conversation(self, conversation: dict) -> None:
        """Insert a new conversation and register it under its user.

        Adds the conversation to ``conversations[conv_id]`` and appends the
        ``conv_id`` to ``users[user_id]`` (creating the list if needed). The
        ``emails_sent`` and ``emails_received`` lists are added if missing.

        Args:
            conversation (dict): Conversation record containing at minimum
                ``conv_id`` (str) and ``user_id`` (str | int). All other
                keys are stored verbatim.

        Returns:
            None

        Example:
            >>> db.insert_conversation({
            ...     "conv_id": "3fa9c1b2",
            ...     "user_id": "42",
            ...     "supplier_email": "buyer@acme.com",
            ...     "status": "open",
            ... })
        """
        with self._lock:
            data = self._read()
            conv_id = conversation["conv_id"]
            user_id = str(conversation["user_id"])
            conversation.setdefault("emails_sent", [])
            conversation.setdefault("emails_received", [])
            data["conversations"][conv_id] = conversation
            data["users"].setdefault(user_id, [])
            if conv_id not in data["users"][user_id]:
                data["users"][user_id].append(conv_id)
            self._write(data)
        self.log.debug(
            "Inserted conversation %s for user %s", conv_id, user_id
        )

    def add_sent_email(self, conv_id: str, email_data: dict) -> None:
        """Append a sent-email record to an existing conversation.

        Silently ignores the call if ``conv_id`` is not found in the store.

        Args:
            conv_id (str): The conversation the email belongs to.
            email_data (dict): Sent-email record. Typical keys include
                ``from_email``, ``to_email``, ``subject``, ``body_html``,
                ``status_code`` and ``sent_at``.

        Returns:
            None

        Example:
            >>> db.add_sent_email("3fa9c1b2", {
            ...     "from_email": "noreply@yourdomain.com",
            ...     "to_email": "buyer@acme.com",
            ...     "subject": "[RFQ-3FA9] Request for Quotation",
            ...     "sent_at": "2025-06-22T08:00:00+00:00",
            ... })
        """
        with self._lock:
            data = self._read()
            if conv_id in data["conversations"]:
                conv = data["conversations"][conv_id]
                conv["emails_sent"].append(email_data)
                self._write(data)
                self.log.debug("Recorded sent email on %s", conv_id)
            else:
                self.log.warning(
                    "add_sent_email: unknown conv_id %s", conv_id
                )

    def add_received_email(self, conv_id: str, email_data: dict) -> None:
        """Append an inbound reply and update the conversation status.

        Also increments ``reply_count``, sets ``last_reply_at`` to the value
        of ``email_data["received_at"]`` and flips ``status`` to
        ``"replied"``. Silently no-ops if ``conv_id`` is not found.

        Args:
            conv_id (str): The conversation the reply belongs to.
            email_data (dict): Inbound email record. Typical keys include
                ``from_email``, ``to_email``, ``subject``, ``body_text``,
                ``body_html``, ``attachments``, ``spam_score`` and
                ``received_at``.

        Returns:
            None

        Example:
            >>> db.add_received_email("3fa9c1b2", {
            ...     "from_email": "buyer@acme.com",
            ...     "body_text": "Our price is $11.50 per unit.",
            ...     "received_at": "2025-06-22T09:15:00+00:00",
            ...     "attachments": [],
            ... })
        """
        with self._lock:
            data = self._read()
            if conv_id not in data["conversations"]:
                self.log.warning(
                    "add_received_email: unknown conv_id %s", conv_id
                )
                return
            conv = data["conversations"][conv_id]
            conv.setdefault("emails_received", [])
            conv["emails_received"].append(email_data)
            conv["reply_count"] = conv.get("reply_count", 0) + 1
            conv["last_reply_at"] = email_data.get("received_at")
            conv["status"] = "replied"
            self._write(data)
        self.log.debug("Recorded inbound reply on %s", conv_id)

    def update_conversation(self, conv_id: str, updates: dict) -> None:
        """Merge ``updates`` into an existing conversation record.

        Performs a shallow merge: existing keys are overwritten and new keys
        are added. Silently no-ops if ``conv_id`` is not found.

        Args:
            conv_id (str): The conversation to update.
            updates (dict): Key-value pairs to merge. Common uses include
                setting ``product_name``, ``quantity``, ``target_price`` and
                ``status``.

        Returns:
            None

        Example:
            >>> db.update_conversation("3fa9c1b2", {"status": "declined"})
        """
        with self._lock:
            data = self._read()
            if conv_id in data["conversations"]:
                data["conversations"][conv_id].update(updates)
                self._write(data)
                self.log.debug("Updated conversation %s", conv_id)

    def insert_unmatched(self, email_data: dict) -> None:
        """Record an inbound email whose ``To`` address did not parse.

        These records accumulate in ``unmatched_emails`` for manual review.

        Args:
            email_data (dict): Inbound payload. Typical keys include
                ``from_email``, ``to_email``, ``subject``, ``received_at``
                and ``needs_review`` (bool).

        Returns:
            None

        Example:
            >>> db.insert_unmatched({
            ...     "from_email": "unknown@sender.com",
            ...     "to_email": "catchall@mail.example.com",
            ...     "received_at": "2025-06-22T10:00:00+00:00",
            ...     "needs_review": True,
            ... })
        """
        with self._lock:
            data = self._read()
            data.setdefault("unmatched_emails", [])
            data["unmatched_emails"].append(email_data)
            self._write(data)
        self.log.info(
            "Stored unmatched inbound email to %s",
            email_data.get("to_email"),
        )

    # ── Read methods ─────────────────────────────────────────────────

    def get_conversation(self, conv_id: str) -> dict | None:
        """Fetch a single conversation by its ID.

        Args:
            conv_id (str): The 8-character hex conversation identifier.

        Returns:
            dict | None: The full conversation record, or ``None`` if not
                found. The record includes ``emails_sent`` and
                ``emails_received`` sub-lists.

        Example:
            >>> conv = db.get_conversation("3fa9c1b2")
            >>> conv["status"]                       # doctest: +SKIP
            'replied'
        """
        return self._read()["conversations"].get(conv_id)

    def get_user_conversations(self, user_id: str) -> list[dict]:
        """Return all conversations for a user, newest first.

        Args:
            user_id (str): The user identifier to look up.

        Returns:
            list[dict]: Conversation records sorted descending by
                ``created_at``. Empty list if the user is unknown.

        Example:
            >>> convs = db.get_user_conversations("42")
            >>> [c["conv_id"] for c in convs]        # doctest: +SKIP
            ['3fa9c1b2', 'a1b2c3d4']
        """
        data = self._read()
        conv_ids = data["users"].get(str(user_id), [])
        convs = [
            data["conversations"][cid]
            for cid in conv_ids
            if cid in data["conversations"]
        ]
        return sorted(
            convs,
            key=lambda c: c.get("created_at", ""),
            reverse=True,
        )

    def get_all_users(self) -> list[dict]:
        """Return a summary record for every user, most active first.

        Each summary contains the ``user_id``, total
        ``conversation_count``, ``replied_count``, ``open_count`` and
        ``last_activity`` (the most recent of ``last_reply_at`` /
        ``created_at`` across all of the user's conversations).

        Returns:
            list[dict]: User summary dicts sorted descending by
                ``last_activity``. Empty list when the store has no users.

        Example:
            >>> users = db.get_all_users()
            >>> users[0]["user_id"]                  # doctest: +SKIP
            '42'
        """
        data = self._read()
        result = []
        for user_id, conv_ids in data["users"].items():
            convs = [data["conversations"].get(cid) for cid in conv_ids]
            convs = [c for c in convs if c]
            last_activity = max(
                (
                    c.get("last_reply_at") or c.get("created_at", "")
                    for c in convs
                ),
                default="",
            )
            replied = sum(
                1 for c in convs if c.get("status") == "replied"
            )
            open_count = sum(
                1 for c in convs if c.get("status") == "open"
            )
            result.append({
                "user_id": user_id,
                "conversation_count": len(convs),
                "replied_count": replied,
                "open_count": open_count,
                "last_activity": last_activity,
            })
        return sorted(
            result,
            key=lambda u: u["last_activity"],
            reverse=True,
        )

    def get_stats(self) -> dict:
        """Return aggregate counts across the entire store.

        Computes every total in a single read pass.

        Returns:
            dict: A dict with four integer keys: ``total_users``,
                ``total_conversations``, ``total_replied`` and
                ``total_open``.

        Example:
            >>> stats = db.get_stats()
            >>> sorted(stats)
            ['total_conversations', 'total_open', 'total_replied', \
'total_users']
        """
        data = self._read()
        convs = list(data["conversations"].values())
        replied = sum(1 for c in convs if c.get("status") == "replied")
        open_count = sum(1 for c in convs if c.get("status") == "open")
        return {
            "total_users": len(data["users"]),
            "total_conversations": len(convs),
            "total_replied": replied,
            "total_open": open_count,
        }
