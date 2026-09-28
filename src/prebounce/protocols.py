"""Host-supplied callbacks and pluggable backends, as minimal typing.Protocols."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from prebounce.settings import ProxyConfig
    from prebounce.types import Result, SmtpReply


class Cache(Protocol):
    """Key/value store with expiry. Values are JSON-safe (Result.to_dict output)."""

    def get(self, key: str) -> Any | None:
        """Return the stored value, or None if missing or expired."""
        ...

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store value for ttl_seconds."""
        ...


class Store(Protocol):
    """Persistence sink for final results."""

    def save(self, result: Result) -> None: ...


class RateLimiter(Protocol):
    """Shared per-server throttle."""

    def acquire(self, key: str) -> bool:
        """Return True if the caller may contact the server identified by key now."""
        ...


class OnResult(Protocol):
    """Called with every result the verifier returns."""

    def __call__(self, result: Result) -> None: ...


class DomainLists(Protocol):
    """Supplies domain lists, all lower-case."""

    def disposable(self) -> frozenset[str]: ...

    def allow(self) -> frozenset[str]:
        """Domains that must never be treated as disposable."""
        ...


class Resolver(Protocol):
    """DNS lookups returning text records.

    MX records are returned as "<preference> <host>" strings (host without trailing dot).
    A, AAAA and TXT records are returned as plain strings.

    Raises prebounce.errors.NXDomain, NoAnswer or DNSTimeout.
    """

    def resolve(self, name: str, rdtype: str) -> list[str]: ...


class SmtpTransport(Protocol):
    """One SMTP connection. Implementations raise prebounce.errors.TransportError/ProxyError."""

    def connect(self, host: str, port: int, timeout: float) -> SmtpReply:
        """Open the connection and return the server greeting."""
        ...

    def send(self, line: str) -> SmtpReply:
        """Send one command line (no CRLF) and return the parsed, possibly multi-line, reply."""
        ...

    def starttls(self, server_hostname: str) -> None:
        """Upgrade the connection to TLS."""
        ...

    def close(self) -> None: ...


TransportFactory = Callable[["ProxyConfig | None"], SmtpTransport]
"""Builds an unconnected transport, optionally routed through the given proxy."""
