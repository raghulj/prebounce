"""Exception hierarchy. Everything the library raises derives from PrebounceError."""

from __future__ import annotations


class PrebounceError(Exception):
    """Base class for all prebounce errors."""


class ConfigurationError(PrebounceError):
    """Settings are invalid or inconsistent."""


class NXDomain(PrebounceError):
    """The DNS name does not exist."""


class NoAnswer(PrebounceError):
    """The DNS name exists but has no records of the requested type."""


class DNSTimeout(PrebounceError):
    """The DNS query timed out or all servers failed."""


class TransportError(PrebounceError):
    """Connecting to or talking with a mail server failed."""


class ProxyError(TransportError):
    """The SOCKS proxy refused, failed or timed out."""
