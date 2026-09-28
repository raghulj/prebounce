# prebounce

**Know before it bounces.** A self-contained email address verification library for Python.

> **Status: pre-alpha, design stage.** Nothing described below is implemented yet. There is no
> release on PyPI, the API shown is a proposal and will change, and every feature is *planned*.
> The repository currently contains the design documents and an empty package skeleton. See the
> [roadmap](docs/roadmap.md).

## Why

Sending to addresses that do not exist damages sender reputation. Hosted verification services
work, but they are separate products with their own limits and data flows. prebounce is meant to
be one function, `verify(address)`, installed with `pip` and running inside your own project, with
your cache, database and background workers doing the heavy lifting.

## Planned features

All planned, none implemented:

- Syntax check, including international addresses; normalisation
- Disposable, role-address and free-mail detection; typo suggestions (`gmial.com` to `gmail.com`)
- DNS checks: MX records, domains that accept no mail, optional blocklist lookups
- SMTP mailbox probing that never sends `DATA`
- Catch-all (accept-all) detection with a random-address probe
- Greylisting handled as a `pending` result your workers retry
- Provider rules (Gmail, Microsoft, Yahoo, security gateways) that report "unknown" rather than guess
- Spam-trap *risk signals* (nobody can confirm a trap)
- SOCKS5 proxy pools, or an optional probe agent, for hosts that block port 25
- Typed result with verdict, send recommendation, confidence, reasons and raw evidence
- Host-owned resources: cache, store, rate limiter and callbacks are supplied by you
- Zero required dependencies; extras for DNS, syntax and SOCKS

## How it works

Each address passes through nine stages in order; any stage may stop early so bad addresses cost
no network probe:

1. Clean up 2. Syntax 3. Local lists 4. Cache 5. Domain lookup 6. Mailbox probe
7. Read replies 8. Score 9. Return and hooks

Details: [docs/pipeline.md](docs/pipeline.md).

## Planned API (proposal)

```python
from prebounce import Verifier

verifier = Verifier(
    cache=my_cache,                # your Redis, memcached or in-memory wrapper
    store=my_store,                # optional: persist final results
    rate_limiter=my_rate_limiter,  # optional: shared per-mail-server limits
    on_result=log_result,          # optional: called with every result
)

result = verifier.verify("jane@example.com")

result.verdict      # "deliverable" | "undeliverable" | "risky" | "unknown"
result.send         # "safe_to_send" | "risky_to_send" | "do_not_send"
result.confidence   # "high" | "medium" | "low"
result.reasons      # e.g. ["mailbox_accepted"]

if result.status == "pending":     # greylisted: your workers retry later
    schedule_retry(result.address, result.resume_token, delay=result.retry_after_seconds)
```

See [docs/results.md](docs/results.md) for the full result object.

## Host callbacks and settings

The library owns logic only: no database, Redis connection, scheduler or workers. You pass small
objects (`cache`, `store`, `rate_limiter`, `on_result`, `domain_lists`), and settings such as
`DNS_ENABLED`, `SMTP_ENABLED`, `SMTP_PROXIES`, `PROBE_AGENT_URL` and `CATCH_ALL_CHECK` switch
network features on. With no settings, only offline checks run. See
[docs/configuration.md](docs/configuration.md).

## Probe IP addresses and proxies

Mail servers judge the IP address that probes them, and many hosts block port 25. The planned
answer is a SOCKS5 proxy pool (or an optional probe agent) so your application's own IP is never
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

v0.1 offline checks, v0.2 DNS, v0.3 SMTP probing, v0.4 proxies and probe agent, v0.5 disposable
list refresh, v1.0 stable API. Details in [docs/roadmap.md](docs/roadmap.md).

## Contributing

Design review is the most valuable contribution at this stage. See [CONTRIBUTING.md](CONTRIBUTING.md)
and the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities per [SECURITY.md](SECURITY.md).

## Licence

MIT, copyright 2026 Raghul Jagannathan. See [LICENSE](LICENSE). Bundled data lists will carry
their own licences; see `src/prebounce/data/NOTICE`.
