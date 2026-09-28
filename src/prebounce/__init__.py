"""prebounce: email address verification for Python (pre-alpha, design stage)."""

from prebounce.cache import MemoryCache
from prebounce.errors import (
    ConfigurationError,
    DNSTimeout,
    NoAnswer,
    NXDomain,
    PrebounceError,
    ProxyError,
    TransportError,
)
from prebounce.protocols import (
    Cache,
    DomainLists,
    OnResult,
    RateLimiter,
    Resolver,
    SmtpTransport,
    Store,
)
from prebounce.settings import ProxyConfig, Settings
from prebounce.types import (
    Confidence,
    DomainInfo,
    Flags,
    MxRecord,
    PendingState,
    ProbeOutcome,
    ProbeResult,
    Reason,
    Result,
    SendRecommendation,
    SmtpReply,
    Status,
    Verdict,
)
from prebounce.verifier import Verifier, verify

__version__ = "0.0.1"

__all__ = [
    "Cache",
    "Confidence",
    "ConfigurationError",
    "DNSTimeout",
    "DomainInfo",
    "DomainLists",
    "Flags",
    "MemoryCache",
    "MxRecord",
    "NXDomain",
    "NoAnswer",
    "OnResult",
    "PendingState",
    "PrebounceError",
    "ProbeOutcome",
    "ProbeResult",
    "ProxyConfig",
    "ProxyError",
    "RateLimiter",
    "Reason",
    "Resolver",
    "Result",
    "SendRecommendation",
    "Settings",
    "SmtpReply",
    "SmtpTransport",
    "Status",
    "Store",
    "TransportError",
    "Verdict",
    "Verifier",
    "__version__",
    "verify",
]
