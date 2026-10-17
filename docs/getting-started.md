# Getting started

> Pre-alpha (0.1.0). Only offline checks and DNS lookups work; mailbox probing is not implemented yet.

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

Settings come from `Settings.from_env()` (variables prefixed `PREBOUNCE_`) or are passed in
explicitly. DNS lookups need the `dns` extra:

```python
from prebounce import Settings, Verifier

verifier = Verifier(Settings(dns_enabled=True))
```

Mailbox probing is not implemented yet: do not set `smtp_enabled`, the probe raises
`NotImplementedError`. See [responsible use](responsible-use.md).

## Plug into your project

Pass a cache and a rate limiter so results and per-server limits are shared across workers; see
[configuration](configuration.md). Once probing exists, run `verify()` in a background task, not a web request: a probe can take
several seconds.
