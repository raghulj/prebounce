"""Public entry point: orchestrates the pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from prebounce.protocols import (
    Cache,
    DomainLists,
    OnResult,
    RateLimiter,
    Resolver,
    Store,
    TransportFactory,
)
from prebounce.settings import Settings
from prebounce.types import Result


class Verifier:
    """Runs syntax, list, DNS and SMTP stages according to settings.

    Defaults: Settings() (offline), MemoryCache, bundled lists, dnspython resolver and socket/SOCKS
    transports built lazily only when the corresponding stage is enabled.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        cache: Cache | None = None,
        store: Store | None = None,
        rate_limiter: RateLimiter | None = None,
        on_result: OnResult | None = None,
        domain_lists: DomainLists | None = None,
        resolver: Resolver | None = None,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self.settings = settings if settings is not None else Settings()
        self.cache = cache
        self.store = store
        self.rate_limiter = rate_limiter
        self.on_result = on_result
        self.domain_lists = domain_lists
        self.resolver = resolver
        self.transport_factory = transport_factory

    def verify(self, address: str, *, resume_token: str | None = None) -> Result:
        """Verify one address. Bad input yields a result, not an exception.

        resume_token continues a previously pending run.
        """
        raise NotImplementedError

    def verify_many(self, addresses: Iterable[str]) -> list[Result]:
        """Verify addresses in order, sharing caches and per-domain lookups."""
        raise NotImplementedError


def verify(address: str) -> Result:
    """Verify with default (offline) settings taken from Settings.from_env()."""
    raise NotImplementedError
