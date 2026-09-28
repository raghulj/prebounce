# Configuration (planned)

Settings are read with `Settings.from_env()` (variables carry the prefix `PREBOUNCE_`, for
example `PREBOUNCE_DNS_ENABLED=true`) or built as `Settings(...)` and passed to
`Verifier(settings=...)`. Invalid combinations raise `ConfigurationError`.

| Setting | Effect |
|---|---|
| *(none)* | Syntax, disposable, role, free-mail and typo checks. No network. |
| `DNS_ENABLED` | Domain and mail-server lookups, plus blocklist lookups |
| `SMTP_ENABLED`, `SMTP_HELO`, `SMTP_MAIL_FROM` | Direct (requires `DNS_ENABLED`) mailbox checks from this machine |
| `SMTP_PROXIES` | JSON list of `{"url", "helo", "mail_from", "providers"}`: mailbox checks through a pool of SOCKS5 proxies, each with its own HELO and sender (recommended) |
| `PROBE_TIMEOUT` | Seconds per SMTP conversation (default 15) |
| `MAX_GREYLIST_ATTEMPTS`, `GREYLIST_DELAY_SECONDS` | Greylist retry budget (default 3 attempts, 330 s) |
| `BLOCKLIST_ZONES` | Comma-separated DNS blocklist zones (needs `DNS_ENABLED`) |
| `CACHE_TTL` | JSON object overriding per-verdict TTLs in seconds: `deliverable`, `undeliverable`, `risky`, `unknown`, `domain` |
| `STRICT_DISPOSABLE` | Treat unlisted-but-suspect domains as disposable |
| `CATCH_ALL_CHECK` | Also test a random address to detect accept-all domains |

## Host callbacks

The protocols live in `prebounce.protocols`. Also there: `Resolver` and `SmtpTransport` for
swapping DNS and SMTP backends.

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
| `cache` | Get/set results (`Result.to_dict()` output) with expiry | `MemoryCache` |
| `store` | Persist each final result | none |
| `rate_limiter` | Cross-worker per-server limits | in-process limiter |
| `on_result` | Called with every result | none |
| `domain_lists` | Supply disposable and allow lists | bundled, refreshable lists |
