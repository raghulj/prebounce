# Disposable domain lists (planned)

Throwaway email services appear weekly, so the list cannot be fixed at release time. The package
will ship a snapshot; the host refreshes it on its own schedule. Source licences are described in
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

- `refresh_domain_lists()` is a plain function the host schedules (cron, RQ, Celery beat, etc.). The
  library never schedules anything.
- Conditional download using HTTP `ETag`: an unchanged list costs one small request.
- **Sanity gate:** an empty, malformed or suddenly shrunk list (under half its previous size) is
  rejected and the old list kept.
- Stored through the host `cache` or `domain_lists` callback so all workers share one copy.

## Merge precedence

1. Normalise entries: lower-case, IDNA form, no trailing dot.
2. `blocked = (primary UNION fakefilter [UNION strict]) MINUS allow lists`. The allow list wins.
3. The host's own allow and block lists override everything.
4. Parent domains match too (`x.tempmail.example` is caught by `tempmail.example`), using the public
   suffix list to stop at the right level.
5. Each result records which list flagged the domain.
