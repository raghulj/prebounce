# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project intends to follow
[Semantic Versioning](https://semver.org/) once it leaves pre-alpha.

## [Unreleased]

### Added
- Project scaffold (package metadata, tooling configuration) and design documentation.
- Address syntax checking (international addresses) and normalisation.
- Role-address, free-mail, typo-suggestion and gibberish detection.
- Bundled disposable and allow lists, with `refresh_domain_lists()` and
  `DisposableLists.load_refreshed()`.
- DNS lookup: MX, null MX, implicit MX fallback and optional blocklist checks.
- Scoring into verdict, send recommendation, confidence and reasons.
- `Verifier`, `verify()` and `verify_many()`; typed `Result` with `to_dict()`/`from_dict()`.
- `MemoryCache` and `Settings.from_env()`.
- `strict_disposable`: opt-in strict list (disposable/disposable-email-domains), bundled and
  refreshable with `refresh_domain_lists(..., strict=True)`; strict-only matches score `medium`
  confidence. `StrictDomainLists` protocol and `match_disposable()`.
- Continuous integration workflow (lint, format, strict typing, tests on Python 3.10-3.13).

### Known limitations
- Mailbox probing (SMTP replies, session, transports, providers, proxies) is not implemented;
  leave `smtp_enabled` off.
