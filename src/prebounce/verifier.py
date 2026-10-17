"""Public entry point: orchestrates the pipeline."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from datetime import datetime, timezone

from prebounce.address import check_syntax, normalize
from prebounce.cache import MemoryCache
from prebounce.dns import default_resolver, lookup_domain
from prebounce.errors import DNSTimeout, PrebounceError
from prebounce.lists import (
    DisposableLists,
    gibberish_score,
    is_free_provider,
    is_role,
    match_disposable,
    suggest_domain,
)
from prebounce.protocols import (
    Cache,
    DomainLists,
    OnResult,
    RateLimiter,
    Resolver,
    SmtpTransport,
    Store,
    TransportFactory,
)
from prebounce.scoring import score
from prebounce.settings import ProxyConfig, Settings
from prebounce.smtp.providers import identify_provider, provider_reliability
from prebounce.smtp.replies import classify_rcpt
from prebounce.smtp.session import probe_mailbox
from prebounce.smtp.transport import SocketTransport, SocksTransport
from prebounce.types import (
    Confidence,
    DomainInfo,
    Flags,
    PendingState,
    ProbeOutcome,
    ProbeResult,
    Reason,
    Result,
    SendRecommendation,
    Status,
    Verdict,
)

_GIBBERISH_THRESHOLD = 0.7
_CACHE_KEY_PREFIX = "prebounce:v1:result:"

# Per-call DNS memo: None records a lookup that timed out.
_DomainMemo = dict[str, DomainInfo | None]


def _default_transport_factory(proxy: ProxyConfig | None) -> SmtpTransport:
    return SocksTransport(proxy.url) if proxy is not None else SocketTransport()


class Verifier:
    """Runs syntax, list, DNS and SMTP stages according to settings.

    Defaults: Settings() (offline), MemoryCache, bundled lists (with the strict list when
    settings.strict_disposable is on), dnspython resolver and socket/SOCKS
    transports built lazily only when the corresponding stage is enabled.

    Exceptions raised by the host's cache, store or on_result callbacks propagate to the caller of
    verify(); the verifier does not swallow them. Whatever happened before the failing callback
    (for example the cache write) is not rolled back.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        cache: Cache | None = None,
        store: Store | None = None,
        rate_limiter: RateLimiter | None = None,
        on_result: OnResult | None = None,
        domain_lists: DomainLists | None = None,
        resolver: Resolver | None = None,
        transport_factory: TransportFactory | None = None,
    ) -> None:
        self.settings = settings if settings is not None else Settings()
        self.cache: Cache = cache if cache is not None else MemoryCache()
        self.store = store
        self.rate_limiter = rate_limiter
        self.on_result = on_result
        self.domain_lists: DomainLists = (
            domain_lists
            if domain_lists is not None
            else DisposableLists.load_bundled(strict=self.settings.strict_disposable)
        )
        self.resolver = resolver
        self.transport_factory = transport_factory

    def verify(self, address: str, *, resume_token: str | None = None) -> Result:
        """Verify one address. Bad input yields a result, not an exception.

        resume_token continues a previously pending run: it is decoded (PrebounceError if
        malformed or issued for another address), the cache read is skipped and the state is
        handed to the mailbox probe. A NotImplementedError from the probe propagates.
        """
        return self._run(address, resume_token, {})

    def verify_many(self, addresses: Iterable[str]) -> list[Result]:
        """Verify addresses in order, sharing caches and per-domain lookups.

        Duplicates (same normalized address) are verified once and share one Result; store and
        on_result run once per unique address. Each domain is looked up at most once per call.
        """
        memo: _DomainMemo = {}
        done: dict[str, Result] = {}
        results: list[Result] = []
        for address in addresses:
            key = normalize(address)[0]
            if key not in done:
                done[key] = self._run(address, None, memo)
            results.append(done[key])
        return results

    def _run(self, address: str, resume_token: str | None, memo: _DomainMemo) -> Result:
        pending = PendingState.from_token(resume_token) if resume_token is not None else None
        normalized, local, domain_name = normalize(address)
        if pending is not None and pending.address != normalized:
            raise PrebounceError("resume token was issued for a different address")

        result = self._pipeline(address, normalized, local, domain_name, pending, memo)
        if self.store is not None:
            self.store.save(result)
        if self.on_result is not None:
            self.on_result(result)
        return result

    def _pipeline(
        self,
        address: str,
        normalized: str,
        local: str,
        domain_name: str,
        pending: PendingState | None,
        memo: _DomainMemo,
    ) -> Result:
        settings = self.settings
        syntax = check_syntax(address)
        if syntax:
            return self._build(address, normalized, "local", Flags(), None, None, syntax=syntax)

        match = match_disposable(
            self.domain_lists, domain_name, strict=self.settings.strict_disposable
        )
        disposable = match is not None
        suggested = suggest_domain(domain_name)
        suggestion = f"{local}@{suggested}" if suggested is not None else None
        flags = Flags(
            free=is_free_provider(domain_name),
            role=is_role(local),
            disposable=disposable,
            gibberish=gibberish_score(local) >= _GIBBERISH_THRESHOLD,
        )
        if disposable:
            return self._build(
                address, normalized, "local", flags, None, None, strict_match=match == "strict"
            )

        key = _CACHE_KEY_PREFIX + normalized.lower()
        if pending is None:
            cached = self._cache_get(key)
            if cached is not None:
                return dataclasses.replace(
                    cached, address=address, normalized=normalized, source="cache"
                )

        info: DomainInfo | None = None
        if settings.dns_enabled:
            if domain_name not in memo:
                try:
                    memo[domain_name] = lookup_domain(domain_name, self._get_resolver(), settings)
                except DNSTimeout:
                    memo[domain_name] = None
            info = memo[domain_name]
            if info is None:
                return self._build(
                    address,
                    normalized,
                    "dns",
                    flags,
                    None,
                    suggestion,
                    extra=(Reason.temporary_failure,),
                )

        probe: ProbeResult | None = None
        provider: str | None = None
        reliability: str | None = None
        probe_reason: Reason | None = None
        if settings.smtp_enabled and self._probe_eligible(info, suggestion):
            assert info is not None  # smtp_enabled implies dns_enabled
            outcome = probe_mailbox(
                normalized,
                info,
                self.transport_factory or _default_transport_factory,
                settings,
                self.rate_limiter,
                pending,
            )
            if isinstance(outcome, PendingState):
                return self._build(
                    address,
                    normalized,
                    "probe",
                    flags,
                    info,
                    suggestion,
                    pending=outcome,
                    extra=(Reason.greylisted,),
                )
            probe = outcome
            provider = identify_provider([m.host for m in info.mx])
            reliability = provider_reliability(provider)
            if probe.reply is not None:
                probe_reason = classify_rcpt(probe.reply)[1]
            flags = dataclasses.replace(flags, catch_all=_catch_all_flag(probe))

        source = "probe" if probe is not None else "dns" if info is not None else "local"
        result = self._build(
            address,
            normalized,
            source,
            flags,
            info,
            suggestion,
            probe=probe,
            probe_reason=probe_reason,
            reliability=reliability,
            provider=provider,
        )
        ttl = settings.cache_ttl.get(result.verdict.value, 0)
        self.cache.set(key, result.to_dict(), ttl)
        return result

    def _build(
        self,
        address: str,
        normalized: str,
        source: str,
        flags: Flags,
        info: DomainInfo | None,
        suggestion: str | None,
        *,
        syntax: tuple[Reason, ...] = (),
        probe: ProbeResult | None = None,
        probe_reason: Reason | None = None,
        reliability: str | None = None,
        provider: str | None = None,
        pending: PendingState | None = None,
        extra: tuple[Reason, ...] = (),
        strict_match: bool = False,
    ) -> Result:
        verdict, send, confidence, reasons = score(
            syntax,
            flags,
            info,
            probe,
            probe_reason,
            reliability,
            suggestion,
            strict_match,
        )
        if pending is not None:
            verdict, send, confidence = (
                Verdict.unknown,
                SendRecommendation.risky_to_send,
                Confidence.low,
            )
        reasons = tuple(dict.fromkeys((*reasons, *extra)))
        return Result(
            address=address,
            normalized=normalized,
            status=Status.pending if pending is not None else Status.complete,
            verdict=verdict,
            send=send,
            confidence=confidence,
            reasons=reasons,
            flags=flags,
            suggestion=suggestion,
            domain=info,
            probe=probe,
            provider=provider,
            source=source,
            pending=pending,
            checked_at=datetime.now(timezone.utc),
        )

    def _cache_get(self, key: str) -> Result | None:
        raw = self.cache.get(key)
        if raw is None:
            return None
        try:
            cached = Result.from_dict(raw)
        except (KeyError, TypeError, ValueError, PrebounceError):
            return None
        # An entry written by a run with fewer stages enabled must not mask this run's evidence.
        if self.settings.dns_enabled and cached.domain is None and not cached.flags.disposable:
            return None
        if (
            self.settings.smtp_enabled
            and cached.probe is None
            and cached.verdict is Verdict.unknown
        ):
            return None
        return cached

    def _get_resolver(self) -> Resolver:
        if self.resolver is None:
            self.resolver = default_resolver()
        return self.resolver

    @staticmethod
    def _probe_eligible(info: DomainInfo | None, suggestion: str | None) -> bool:
        return (
            info is not None
            and info.exists
            and bool(info.mx)
            and not info.null_mx
            and not info.blocklisted
            and suggestion is None
        )


def _catch_all_flag(probe: ProbeResult) -> bool | None:
    if probe.catch_all is ProbeOutcome.accepted:
        return True
    if probe.catch_all is ProbeOutcome.refused:
        return False
    return None


_default_verifier: Verifier | None = None


def verify(address: str) -> Result:
    """Verify with default (offline) settings taken from Settings.from_env().

    The Verifier is created on first use and reused, so its cache persists across calls.
    """
    global _default_verifier
    if _default_verifier is None:
        _default_verifier = Verifier(Settings.from_env())
    return _default_verifier.verify(address)
