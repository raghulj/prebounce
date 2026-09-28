# Comparison

Neutral feature comparison. The first column is the **plan**, not a shipped product. Cells are
based on public documentation as we read it; `?` means not confirmed. Please open an issue to
correct anything.

Compared: EmailHippo (hosted commercial API, "MORE" product), Reacher (Rust, AGPL or commercial
licence) and AfterShip email-verifier (Go, MIT). Only techniques and public behaviour were studied;
no code from these projects is used.

| Feature | prebounce (planned) | EmailHippo | Reacher | AfterShip |
|---|---|---|---|---|
| Syntax | Yes | Yes (16 reason codes) | Yes | Yes |
| International addresses | Yes, via email-validator | Yes | ? | ? |
| Typo suggestion | Yes | No | ? | Yes |
| Role address | Yes | Yes | Yes | Yes |
| Free-mail provider | Yes | Yes | ? | Yes |
| Disposable domain | Yes, refreshable merged lists | Yes | Yes | Yes |
| Gibberish detection | Partly (heuristic) | Yes | No | No |
| MX / no-mail domains | Yes | Yes | Yes | Yes |
| Domain blocklist | Partly (optional) | Yes | No | No |
| Provider identification | Yes | Yes | Yes | Partly |
| Mailbox exists | Yes (direct, proxy or agent) | Yes | Yes | Yes (optional) |
| Catch-all detection | Yes | Yes | Yes | Yes |
| Greylisting | Yes: pending, host retries | Partly (no retry in real-time API) | ? | ? |
| Mailbox full | Yes | Yes | Yes | ? |
| Security gateways | Yes | Partly | Yes | ? |
| Microsoft and Yahoo | Partly (unknown/risky) | Partly | Yes (browser-based techniques) | Partly |
| Spam traps | Partly (risk signals only) | Partly | No | No |
| Dark-web exposure | No | Yes | No | No |
| Send recommendation | Yes | Yes | Partly | Partly |
| Raw server evidence | Yes | No | Yes | ? |
| Gravatar | Partly (optional) | Yes | Yes | Yes |
| Form | Python library + optional probe agent | Hosted web API | Rust service | Go library |
| Uses host cache/DB/workers | Yes, via callbacks | No | No (own queue) | Partly (in-process) |
| Works where port 25 is blocked | Yes, via proxy or agent | Yes (their servers) | Partly (needs port 25 or paid proxy) | No |
| Licence | MIT | Commercial | AGPL or commercial | MIT |
| Cost | Free software; you pay for any proxies/servers | Per-check pricing | Free self-hosted plus proxies | Free |

The library aims for parity on checks that can be done honestly, and is deliberately more
conservative about claims that cannot be verified (spam traps, consumer-provider mailboxes).
