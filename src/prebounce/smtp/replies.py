"""SMTP reply parsing and RCPT classification."""

from __future__ import annotations

from prebounce.types import ProbeOutcome, Reason, SmtpReply


def parse_reply(lines: list[str]) -> SmtpReply:
    """Parse raw reply lines ("250-first", "250 last") into one SmtpReply.

    text joins the line texts with newlines; enhanced is the RFC 3463 code if present.
    Raises TransportError on malformed input.
    """
    raise NotImplementedError


def classify_rcpt(reply: SmtpReply) -> tuple[ProbeOutcome, Reason | None]:
    """Classify a RCPT TO reply.

    2xx -> (accepted, mailbox_accepted); 550 5.1.1 style -> (refused, mailbox_not_found);
    full/disabled -> (refused, mailbox_full / mailbox_disabled); 4xx -> (inconclusive,
    greylisted or temporary_failure); policy/blocked 5xx -> (inconclusive, prober_blocked).
    """
    raise NotImplementedError
