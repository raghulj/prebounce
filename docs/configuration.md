# Configuration (planned)

Settings are read from environment variables or passed to `Verifier(settings=...)`. Names are
provisional.

| Setting | Effect |
|---|---|
| *(none)* | Syntax, disposable, role, free-mail and typo checks. No network. |
| `DNS_ENABLED` | Domain and mail-server lookups, plus blocklist lookups |
| `SMTP_ENABLED`, `SMTP_HELO`, `SMTP_MAIL_FROM` | Direct mailbox checks from this machine |
| `SMTP_PROXIES` | Mailbox checks through a pool of SOCKS5 proxies, each with its own HELO and sender (recommended) |
| `PROBE_AGENT_URL`, `PROBE_AGENT_TOKEN` | Mailbox checks through a probe agent over HTTPS |
| `CATCH_ALL_CHECK` | Also test a random address to detect accept-all domains |

## Host callbacks

Sketches only; the real protocols may differ.

```python
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...


class Store(Protocol):
    def save(self, result: "Result") -> None: ...


class RateLimiter(Protocol):
    def acquire(self, key: str) -> bool:
        """May we contact this mail server now? Shared across workers."""


class OnResult(Protocol):
    def __call__(self, result: "Result") -> None: ...


class DomainLists(Protocol):
    def disposable(self) -> frozenset[str]: ...
    def allow(self) -> frozenset[str]: ...
```

| Callback | Purpose | Default |
|---|---|---|
| `cache` | Get/set results with expiry | in-memory |
| `store` | Persist each final result | none |
| `rate_limiter` | Cross-worker per-server limits | in-process limiter |
| `on_result` | Called with every result | none |
| `domain_lists` | Supply disposable and allow lists | bundled, refreshable lists |
