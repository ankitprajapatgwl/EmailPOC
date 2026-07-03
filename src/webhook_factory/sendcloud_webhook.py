"""Inbound webhook parser placeholder for SendCloud.

SendCloud's inbound-mail webhook payload format has not been documented in
this repo yet (only the outbound *Basic Send* API has). This parser exists
solely so that :class:`~src.webhook_factory.factory.WebhookParserFactory`
recognises ``"sendcloud"`` and the application can start up with
``EMAIL_PROVIDER=sendcloud`` selected — outbound sending works, but any
inbound POST to ``/webhooks/inbound`` fails clearly instead of being
(mis)parsed.

Replace :meth:`SendCloudWebhookParser.parse` with a real implementation once
SendCloud's inbound webhook payload shape is available.

Example:
    >>> from src.webhook_factory.sendcloud_webhook import (
    ...     SendCloudWebhookParser)
    >>> parser = SendCloudWebhookParser(settings, logger)  # doctest: +SKIP
    >>> parser.provider_name
    'sendcloud'
"""

from fastapi import Request

from src.webhook_factory.webhook_master import (
    InboundEmail,
    WebhookParseError,
    WebhookParserMaster,
)


class SendCloudWebhookParser(WebhookParserMaster):
    """Not-yet-implemented inbound parser for SendCloud.

    Inherits attachment persistence and the default (trusted) signature
    check from :class:`WebhookParserMaster`, but :meth:`parse` always raises
    until a real implementation replaces this stub.

    Example:
        >>> parser = SendCloudWebhookParser(settings, logger)
        >>> parser.provider_name
        'sendcloud'
    """

    @property
    def provider_name(self) -> str:
        """Return the provider key ``"sendcloud"``.

        Returns:
            str: Always ``"sendcloud"``.
        """
        return "sendcloud"

    async def parse(self, request: Request) -> InboundEmail:
        """Reject the inbound payload with a clear "not implemented" error.

        Args:
            request (Request): The FastAPI request for the inbound POST
                (unread — there is nothing to parse yet).

        Returns:
            InboundEmail: Never returns.

        Raises:
            WebhookParseError: Always. SendCloud inbound parsing has not
                been implemented because no inbound webhook payload doc has
                been provided yet.
        """
        raise WebhookParseError(
            "SendCloud inbound webhook parsing is not implemented yet. "
            "Outbound sending via SendCloud works; provide SendCloud's "
            "inbound webhook payload doc to add support for parsing "
            "supplier replies."
        )
