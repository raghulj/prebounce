# Disposable domain lists

Bundled snapshot, `refresh_domain_lists()` and the opt-in strict list are implemented.

Throwaway email services appear weekly, so the list cannot be fixed at release time. The package
ships a snapshot; the host refreshes it on its own schedule. Source licences are described in
`src/prebounce/data/NOTICE`.

## Sources

| Source | Licence | Role |
|---|---|---|
| disposable-email-domains/disposable-email-domains | CC0 | Primary; curated, lowest false-positive risk |
| 7c/fakefilter | BSD-3 | Coverage; first/last-seen metadata |
| disposable/disposable-email-domains (`domains.txt`) | MIT | Optional opt-in "strict" list; larger, more false positives |
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
- The strict source (about 1.5 MB) is fetched only with `refresh_domain_lists(fetch, store,
  strict=True)` and read back only with `load_refreshed(cache, strict=True)`.

## Merge precedence

1. Normalise entries: lower-case, IDNA form, no trailing dot.
2. `blocked = (primary UNION fakefilter [UNION strict]) MINUS allow lists`. The allow list wins.
3. The host's own allow and block lists override everything.
4. Parent domains match too (`x.tempmail.example` is caught by `tempmail.example`), without a public suffix
   list (the walk stops before the bare TLD).
5. A domain flagged by the core lists gets `high` confidence; one flagged only by the strict list
   gets `medium`.

## Strict mode

`STRICT_DISPOSABLE` (or `Settings(strict_disposable=True)`) also checks the
[disposable/disposable-email-domains](https://github.com/disposable/disposable-email-domains)
`domains.txt` list: about 96,000 domains, roughly 84,000 of them not on the core lists. It catches
more burner domains, and also more small domains that are not disposable at all.

- Off by default. The bundled strict file is read only when it is on, so it costs no memory
  otherwise.
- That project's `domains_strict.txt` is deliberately not used: it adds freemail providers such as
  outlook.com and hotmail.com. Free providers and allow-listed domains are never flagged either way.
- A match only on the strict list gives `undeliverable`, `do_not_send`, reason
  `disposable_domain`, confidence `medium`.
- Suits signup forms. For imported customer lists, leave it off or review `medium` results.
- A custom `domain_lists` object takes part only if it has a `strict()` method
  (`prebounce.StrictDomainLists`); otherwise strict mode adds nothing.
