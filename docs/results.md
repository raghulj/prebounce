# Results (planned)

`verify()` returns a typed, immutable result object. Field names are provisional.

## Fields

| Field | Meaning |
|---|---|
| `address` | Normalised address |
| `status` | `"complete"` or `"pending"` |
| `verdict` | `deliverable`, `undeliverable`, `risky`, `unknown` |
| `send` | Recommendation: `safe_to_send`, `risky_to_send`, `do_not_send` |
| `confidence` | `high`, `medium`, `low` |
| `flags` | `free`, `role`, `disposable`, `catch_all` booleans |
| `reasons` | Machine-readable codes such as `mailbox_accepted`, `disposable_domain`, `domain_not_found`, `accept_all`, `security_gateway`, `greylisted`, `provider_unreliable`, `mailbox_full`, `prober_blocked`, `syntax_*` |
| `risk_signals` | e.g. `typo_domain`, `possible_typo_trap`; never a claim that a trap is confirmed |
| `suggestion` | Corrected address for typo domains |
| `provider` | Detected mail provider, if any |
| `source` | Where the deciding evidence came from: `local`, `dns`, `probe`, combinations |
| `evidence` | Raw server reply lines for probe results |

## Verdicts and recommendations

- `deliverable` with `safe_to_send`: the mailbox was accepted and the domain is not accept-all.
- `undeliverable` with `do_not_send`: bad syntax, nonexistent domain, disposable domain, or a permanent "no such user".
- `risky`: exists but with caveats: accept-all domain, full mailbox, typo domain, role address on a gateway.
- `unknown`: no reliable answer, for example providers that answer probes inconsistently, or the prober was blocked. The library never reports a blocked prober as "invalid".

## Pending results

Greylisting (a temporary 4xx refusal) yields `status == "pending"` with `retry_after_seconds`,
`attempt`, `max_attempts` and an opaque `resume_token`. The library never sleeps or schedules;
the host re-invokes verification later, passing the token, ideally through the same proxy/IP and
sender, because the remote server remembers them.

```json
{"address": "lee@greylist-sample.org", "status": "pending", "retry_after_seconds": 330,
 "attempt": 1, "max_attempts": 3, "resume_token": "...", "reasons": ["greylisted"]}
```
