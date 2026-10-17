# prebounce

**Know before it bounces.** A self-contained email address verification library for Python.

> **Status: pre-alpha.** The offline checks, DNS lookups, scoring and the `Verifier` API are
> implemented and tested. Mailbox probing (the `smtp` package: reply handling, session, transports,
> providers, proxies) is **not implemented yet**; keep `smtp_enabled` off. Released on PyPI as
> `prebounce` 0.1.0; the API may still change. See the [roadmap](docs/roadmap.md).

## Why

Sending to addresses that do not exist damages sender reputation. Hosted verification services
work, but they are separate products with their own limits and data flows. prebounce is meant to
be one function, `verify(address)`, installed with `pip` and running inside your own project, with
your cache, database and background workers doing the heavy lifting.

## Features

Implemented:

- Syntax check, including international addresses; normalisation
- Disposable, role-address and free-mail detection; typo suggestions (`gmial.com` to `gmail.com`);
  gibberish score
- Bundled disposable and allow lists, plus `refresh_domain_lists()` for host-scheduled refreshes
- DNS checks: MX records, null MX, implicit MX fallback, optional blocklist lookups
- Scoring into a typed result with verdict, send recommendation, confidence, reasons and flags
- `Verifier`, `verify()` and `verify_many()`; `MemoryCache`; `Settings.from_env()`
- Host-owned resources: cache, store, rate limiter and callbacks are supplied by you
- Zero required dependencies; extras for DNS, syntax and SOCKS

Not implemented yet (design only, see the linked docs):

- SMTP mailbox probing that never sends `DATA`, catch-all detection, greylisting as a `pending`
  result, provider rules ([smtp-probing](docs/smtp-probing.md))
- SOCKS5 proxy pools or a probe agent ([proxies](docs/proxies.md))
- Spam-trap *risk signals*

## How it works

Each address passes through nine stages in order; any stage may stop early so bad addresses cost
no network probe:

1. Clean up 2. Syntax 3. Local lists 4. Cache 5. Domain lookup 6. Mailbox probe
7. Read replies 8. Score 9. Return and hooks

Details: [docs/pipeline.md](docs/pipeline.md).

## Usage

```python
from prebounce import MemoryCache, Verifier, verify

result = verify("jane@example.com")  # offline checks only, default settings

verifier = Verifier(
    cache=MemoryCache(),  # or your Redis/memcached wrapper
    on_result=print,  # optional: called with every result
)

result = verifier.verify("jane@example.com")

result.verdict  # Verdict: deliverable | undeliverable | risky | unknown
result.send  # SendRecommendation: safe_to_send | risky_to_send | do_not_send
result.confidence  # Confidence: high | medium | low
result.reasons  # tuple of Reason values

results = verifier.verify_many(["a@example.com", "b@example.org"])
```

Greylisted results (`result.status == Status.pending`, resumed with
`verify(..., resume_token=result.pending.to_token())`) only occur once mailbox probing exists.

See [docs/results.md](docs/results.md) for the full result object.

## Host callbacks and settings

The library owns logic only: no database, Redis connection, scheduler or workers. You pass small
objects (`cache`, `store`, `rate_limiter`, `on_result`, `domain_lists`), and settings such as
`DNS_ENABLED`, `SMTP_ENABLED`, `SMTP_PROXIES` and `CATCH_ALL_CHECK` switch
network features on (`DNS_ENABLED` works today; the `SMTP_*` and `CATCH_ALL_CHECK` settings only
matter once probing exists; a probe agent setting does not exist yet). With no settings, only offline checks
run. See
[docs/configuration.md](docs/configuration.md).

## Probe IP addresses and proxies

Mail servers judge the IP address that probes them, and many hosts block port 25. The planned
answer (not implemented yet) is a SOCKS5 proxy pool (or an optional probe agent) so your application's own IP is never
the one seen. See [docs/proxies.md](docs/proxies.md) and
[docs/responsible-use.md](docs/responsible-use.md).

## Documentation

[Index](docs/index.md) | [Getting started](docs/getting-started.md) | [Pipeline](docs/pipeline.md) |
[Results](docs/results.md) | [Configuration](docs/configuration.md) |
[SMTP probing](docs/smtp-probing.md) | [Proxies](docs/proxies.md) |
[Disposable domains](docs/disposable-domains.md) | [Comparison](docs/comparison.md) |
[Responsible use](docs/responsible-use.md) | [Roadmap](docs/roadmap.md) |
[Design decisions](docs/design-decisions.md)

## Roadmap

v0.1 offline checks, v0.2 DNS and v0.5 list refresh are released in 0.1.0;
v0.3 SMTP probing and v0.4 proxies and probe agent are not started; v1.0 stable API. Details in [docs/roadmap.md](docs/roadmap.md).

## Contributing

Design review and bug reports are the most valuable contributions at this stage. See [CONTRIBUTING.md](CONTRIBUTING.md)
and the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities per [SECURITY.md](SECURITY.md).

## Licence

MIT, copyright 2026 Raghul Jagannathan. See [LICENSE](LICENSE). Bundled data lists will carry
their own licences; see `src/prebounce/data/NOTICE`.
