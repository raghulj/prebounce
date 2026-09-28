# Getting started (planned)

> Nothing here works yet; this is the intended experience. There is no PyPI release.

## Install

    pip install prebounce                 # core: offline checks, no dependencies
    pip install "prebounce[syntax]"       # email-validator for full RFC syntax checks
    pip install "prebounce[dns]"          # dnspython for MX and blocklist lookups
    pip install "prebounce[socks]"        # python-socks for SOCKS5 proxy support

## Offline only

With no settings, only checks needing no network run (syntax, lists, typos):

```python
from prebounce import Verifier

result = Verifier().verify("jane@example.com")
print(result.verdict, result.send)
```

## Turn on network features

Settings come from environment variables or are passed in explicitly:

```python
verifier = Verifier(settings={"DNS_ENABLED": True})
```

Mailbox probing needs one of: direct SMTP, a SOCKS5 proxy pool, or a probe agent. Read
[responsible use](responsible-use.md) and [proxies](proxies.md) first.

## Plug into your project

Pass a cache and a rate limiter so results and per-server limits are shared across workers; see
[configuration](configuration.md). Run `verify()` inside a background task, never in a web request:
a probe can take several seconds.
