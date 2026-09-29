# Disposable domain lists

Bundled snapshot and `refresh_domain_lists()` are implemented. The opt-in strict list is not
(`strict_disposable` is accepted but not yet wired).

Throwaway email services appear weekly, so the list cannot be fixed at release time. The package
ships a snapshot; the host refreshes it on its own schedule. Source licences are described in
`src/prebounce/data/NOTICE`.

## Sources

| Source | Licence | Role |
|---|---|---|
| disposable-email-domains/disposable-email-domains | CC0 | Primary; curated, lowest false-positive risk |
| 7c/fakefilter | BSD-3 | Coverage; first/last-seen metadata |
| disposable/disposable-email-domains | MIT | Optional opt-in "strict" list; larger, more false positives |
| amieiro/disposable-email-domains | MIT | Allow list only (`allowDomains.txt`) |

Manually maintained lists were judged slower and less reliable and are not planned sources. Domain
counts and update cadence change constantly; check upstream rather than trusting this document.

## Refresh

- `refresh_domain_lists(fetch, store)` (in `prebounce.lists`) is a plain function the host schedules (cron, RQ, Celery beat, etc.). The
  library never schedules anything.
- The host supplies `fetch(url) -> text`, so the library opens no sockets; conditional requests
  (`ETag`) are up to the host's fetch function.
- **Sanity gate:** an empty, malformed or suddenly shrunk list (under half its previous size) is
  rejected and the old list kept.
- Saved in a host `Cache`; `DisposableLists.load_refreshed(cache)` reads it back so all workers
  share one copy.

## Merge precedence

1. Normalise entries: lower-case, IDNA form, no trailing dot.
2. `blocked = (primary UNION fakefilter [UNION strict]) MINUS allow lists`. The allow list wins.
3. The host's own allow and block lists override everything.
4. Parent domains match too (`x.tempmail.example` is caught by `tempmail.example`), without a public suffix
   list (the walk stops before the bare TLD).
5. Each result records which list flagged the domain.
