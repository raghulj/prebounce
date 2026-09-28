# The verification pipeline (planned)

Every address passes through the same nine stages in order. A stage may stop early with a firm
answer, so bad addresses never cost a network probe.

| # | Stage | Cost | What it does | Stops when | Needs |
|---|---|---|---|---|---|
| 1 | Clean up | free, instant | Trims spaces, lower-cases the domain, converts international characters to a standard form, splits user and domain | never | nothing |
| 2 | Syntax | free, instant | Checks RFC 5322 / 6531 rules: international addresses, length limits, dots, quoting (via `email-validator` when installed) | invalid format: undeliverable | nothing |
| 3 | Local lists | free, instant | Disposable, role-address (`info@`, `sales@`) and free-mail lists; typo suggestions (`gmial.com` to `gmail.com`); gibberish score | disposable domain: do not send; other checks add flags only | bundled lists, refreshed on a schedule |
| 4 | Cache | free, one lookup | Asks the host cache for an unexpired earlier result | fresh result found: return it | host `cache` (optional) |
| 5 | Domain lookup | ~10-100 ms, cached per domain | Finds mail servers, handles domains declaring they take no mail, falls back to the domain's own address, optionally checks blocklists and domain age | no domain or no mail servers: undeliverable | `DNS_ENABLED` |
| 6 | Mailbox probe | ~0.3-8 s, rate-limited per server | Asks the mail server about the address, then a random address (catch-all test), hangs up before sending | temporary refusal: pending | direct SMTP, `SMTP_PROXIES` or `PROBE_AGENT_URL` |
| 7 | Read replies | free | Maps reply codes/text to meanings (accepted, no such user, mailbox full, greylisted, prober blocked); applies provider rules | never | bundled provider table |
| 8 | Score | free | Combines everything into verdict, send recommendation, confidence and risk signals | never | nothing |
| 9 | Return and hooks | free | Writes to the cache with an expiry, calls `store` and `on_result`, returns a typed result | never | host callbacks (optional) |

## Illustrative traces

These are examples of intended behaviour, not recorded output.

- `temp@mailinator.com`: stage 3 finds a disposable domain and stops. Undeliverable, do not send, no network.
- `bob@@example.com`: stage 2 stops on a second `@`.
- `jane@gmial.com`: typo domain; probe skipped; risky, do not send, suggestion `jane@gmail.com`.
- `info@acme-sample.com`: role address, security-gateway mail servers, both probes accepted; risky, accept-all.
- `lee@greylist-sample.org`: server answers 450 greylisted; result is `pending`, retried by the host.
- `amy@outlook.com`: provider answers are unreliable; unknown, risky to send.

Stages 5 and 6 are skipped entirely when their settings are off, and the result says so in its
`source` and `checks_run` fields (see [results](results.md)).
