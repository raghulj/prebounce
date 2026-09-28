"""Turns collected evidence into a verdict, recommendation, confidence and reasons."""

from __future__ import annotations

from prebounce.types import (
    Confidence,
    DomainInfo,
    Flags,
    ProbeResult,
    Reason,
    SendRecommendation,
    Verdict,
)


def score(
    syntax: tuple[Reason, ...],
    flags: Flags,
    domain: DomainInfo | None,
    probe: ProbeResult | None,
    probe_reason: Reason | None,
    provider_reliability: str | None,
    suggestion: str | None,
    strict_disposable: bool,
) -> tuple[Verdict, SendRecommendation, Confidence, tuple[Reason, ...]]:
    """Combine evidence. Pure function.

    probe_reason is the second value of smtp.replies.classify_rcpt; provider_reliability is one of
    "reliable", "unreliable", "accept_all_gateway" or None. A blocked or failed probe never yields
    undeliverable.
    """
    raise NotImplementedError
