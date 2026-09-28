# Roadmap

All milestones are planned; none are started. Order and scope may change.

| Version | Theme | Contents |
|---|---|---|
| v0.1 | Offline checks | Normalisation, syntax, disposable/role/free-mail lists (snapshot), typo suggestions, result types, cache callback |
| v0.2 | DNS | MX and no-mail domains, fallback to domain address, optional blocklists and domain age, per-domain caching |
| v0.3 | SMTP probing | Direct probe (no `DATA`), reply interpretation, catch-all detection, greylisting as `pending`, provider rules, gateways, rate limiter callback |
| v0.4 | Proxies and agent | SOCKS5 pools with per-provider routing and health tracking, optional probe agent over HTTPS |
| v0.5 | List refresh | `refresh_domain_lists()`, ETag, sanity gate, merge precedence, strict mode |
| v1.0 | Stable | Stable API and result schema, documented deprecation policy, complete docs |

Later ideas: async wrapper, more provider rules, a CLI.
