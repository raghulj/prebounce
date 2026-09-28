"""DNS: domain existence, MX discovery and blocklist lookups."""

from __future__ import annotations

from prebounce.protocols import Resolver
from prebounce.settings import Settings
from prebounce.types import DomainInfo


def lookup_domain(domain: str, resolver: Resolver, settings: Settings) -> DomainInfo:
    """Resolve MX (falling back to implicit A/AAAA MX), detect null MX and query blocklist_zones.

    A missing domain returns DomainInfo(exists=False); DNSTimeout propagates.
    """
    raise NotImplementedError


def default_resolver() -> Resolver:
    """Return a dnspython-backed Resolver. Raises ConfigurationError if dnspython is missing."""
    raise NotImplementedError
