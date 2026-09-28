"""Mail provider identification and how far to trust its probe answers."""

from __future__ import annotations

from collections.abc import Iterable


def identify_provider(mx_hosts: Iterable[str]) -> str | None:
    """Return a provider id (e.g. "google", "microsoft", "proofpoint") from MX hostnames."""
    raise NotImplementedError


def provider_reliability(provider: str | None) -> str:
    """Return "reliable", "unreliable" or "accept_all_gateway"; unknown providers are "reliable"."""
    raise NotImplementedError
