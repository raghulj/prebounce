"""Runs a mailbox probe conversation."""

from __future__ import annotations

from prebounce.protocols import RateLimiter, TransportFactory
from prebounce.settings import Settings
from prebounce.types import DomainInfo, PendingState, ProbeResult


def probe_mailbox(
    address: str,
    domain_info: DomainInfo,
    transport_factory: TransportFactory,
    settings: Settings,
    rate_limiter: RateLimiter | None,
    pending: PendingState | None,
) -> ProbeResult | PendingState:
    """Probe address against its MX hosts.

    Returns ProbeResult when finished (including inconclusive/not_run outcomes) or a PendingState
    when the server greylisted and attempts remain. Never sleeps. When pending is given, reuse its
    proxy and mx_host. Connection failures become an inconclusive ProbeResult, not exceptions.
    """
    raise NotImplementedError
