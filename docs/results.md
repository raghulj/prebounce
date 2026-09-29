# Results

Everything except probe-derived data is implemented. `probe`, `catch_all`, `pending` and the
reasons that come from a mailbox probe (`mailbox_accepted`, `accept_all`, `greylisted`,
`mailbox_full`, `prober_blocked`, ...) exist as types but are not produced until probing is
implemented.

`verify()` returns a typed, immutable result object. Types live in `prebounce.types`; `Result.to_dict()` / `Result.from_dict()` round-trip through JSON.

## Fields

| Field | Meaning |
|---|---|
| `address` | The address as given |
| `normalized` | Trimmed address with lower-cased domain |
| `status` | `"complete"` or `"pending"` |
| `verdict` | `deliverable`, `undeliverable`, `risky`, `unknown` |
| `send` | Recommendation: `safe_to_send`, `risky_to_send`, `do_not_send` |
| `confidence` | `high`, `medium`, `low` |
| `flags` | `free`, `role`, `disposable`, `gibberish` booleans and `catch_all` (`true`, `false` or `null` when untested) |
| `reasons` | Machine-readable codes such as `mailbox_accepted`, `disposable_domain`, `domain_not_found`, `accept_all`, `security_gateway`, `greylisted`, `provider_unreliable`, `mailbox_full`, `prober_blocked`, `typo_domain`, `possible_typo_trap` (never a claim that a trap is confirmed), `syntax_*`; the full list is the `Reason` enum |
| `suggestion` | Corrected address for typo domains |
| `provider` | Detected mail provider, if any |
| `source` | Where the deciding evidence came from: `local`, `dns`, `probe` or `cache` |
| `domain` | `DomainInfo`: MX records, null MX, blocklist hits |
| `probe` | `ProbeResult`: outcome, server reply, catch-all outcome, MX host, proxy, transcript lines |
| `pending` | `PendingState` when `status == "pending"`; `pending.to_token()` is the resume token |
| `checked_at` | UTC timestamp |

## Verdicts and recommendations

- `deliverable` with `safe_to_send`: the mailbox was accepted and the domain is not accept-all.
- `undeliverable` with `do_not_send`: bad syntax, nonexistent domain, disposable domain, or a permanent "no such user".
- `risky`: exists but with caveats: accept-all domain, full mailbox, typo domain, role address on a gateway.
- `unknown`: no reliable answer, for example providers that answer probes inconsistently, or the prober was blocked. The library never reports a blocked prober as "invalid".

## Pending results

Greylisting (a temporary 4xx refusal) yields `status == "pending"` with a `PendingState` in
`pending` (`retry_after_seconds`, `attempt`, `max_attempts`, plus the opaque token from
`to_token()`; pass it as `verify(..., resume_token=...)`). The library never sleeps or schedules;
the host re-invokes verification later, passing the token, ideally through the same proxy/IP and
sender, because the remote server remembers them.

```json
{"address": "lee@greylist-sample.org", "status": "pending", "retry_after_seconds": 330,
 "attempt": 1, "max_attempts": 3, "resume_token": "...", "reasons": ["greylisted"]}
```
