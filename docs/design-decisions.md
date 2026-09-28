# Design decisions

## Sync-first with a sans-I/O core

The public API is synchronous. Parsing, interpretation and scoring are pure functions of bytes and
data, with I/O (sockets, DNS, HTTP) at the edges. This keeps the logic testable offline and lets
an async wrapper be added later without a rewrite.

## Host-owned resources

The library has no database, Redis connection, scheduler or workers. The host passes a cache,
store, rate limiter and callbacks. This avoids dictating infrastructure and keeps cross-worker
state (rate limits, proxy health, lists) where the host already manages it.

## No scheduler

Retries for greylisting and list refreshes are plain functions the host calls on its own schedule
(cron, Celery, RQ, or anything else). The library returns `retry_after_seconds` and never sleeps.

## Zero required dependencies

The core uses the standard library. `dnspython`, `email-validator` and `python-socks` are optional
extras.

## Honest results

Unknown stays unknown. Consumer providers with unreliable probe answers, blocked probers and spam
traps are reported as such, not guessed.

## Clean-room implementation

Other open-source verifiers were studied for technique only. No code, data tables or fixtures are
copied, notably from copyleft (AGPL) projects. Behaviour is derived from RFCs and observed public
protocol behaviour.
