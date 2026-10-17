"""Verifier pipeline tests: fake resolver, MemoryCache and recording callbacks; no network."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from prebounce import address as address_mod
from prebounce import verifier as verifier_mod
from prebounce.cache import MemoryCache
from prebounce.errors import DNSTimeout, NXDomain, PrebounceError
from prebounce.lists import DisposableLists
from prebounce.settings import Settings
from prebounce.types import (
    Confidence,
    DomainInfo,
    MxRecord,
    PendingState,
    ProbeOutcome,
    ProbeResult,
    Reason,
    Result,
    SendRecommendation,
    SmtpReply,
    Status,
    Verdict,
)
from prebounce.verifier import Verifier

KEY = "prebounce:v1:result:"


class FakeResolver:
    def __init__(self, records: dict[tuple[str, str], list[str] | Exception] | None = None) -> None:
        self.records = records or {}
        self.calls: list[tuple[str, str]] = []

    def resolve(self, name: str, rdtype: str) -> list[str]:
        self.calls.append((name, rdtype))
        value = self.records.get((name, rdtype), NXDomain(name))
        if isinstance(value, Exception):
            raise value
        return value

    def domains_queried(self) -> list[str]:
        return [n for n, t in self.calls if t == "MX"]


class Recorder:
    def __init__(self) -> None:
        self.saved: list[Result] = []
        self.seen: list[Result] = []

    def save(self, result: Result) -> None:
        self.saved.append(result)

    def __call__(self, result: Result) -> None:
        self.seen.append(result)


class SpyCache(MemoryCache):
    def __init__(self) -> None:
        super().__init__()
        self.ttls: dict[str, int] = {}

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.ttls[key] = ttl_seconds
        super().set(key, value, ttl_seconds)


DNS_SETTINGS = Settings(dns_enabled=True)
SMTP_SETTINGS = Settings(
    dns_enabled=True, smtp_enabled=True, smtp_helo="h.test", smtp_mail_from="a@h.test"
)


def resolver() -> FakeResolver:
    return FakeResolver(
        {
            ("example.com", "MX"): ["10 mx.example.com"],
            ("nomx.test", "MX"): ["0 ."],
            ("slow.test", "MX"): DNSTimeout("slow.test"),
        }
    )


def make(
    settings: Settings | None = None,
    res: FakeResolver | None = None,
    cache: MemoryCache | None = None,
) -> tuple[Verifier, Recorder, FakeResolver]:
    rec = Recorder()
    res = res or resolver()
    v = Verifier(settings, cache=cache, store=rec, on_result=rec, resolver=res)
    return v, rec, res


# --- stop points


def test_syntax_stop() -> None:
    v, rec, res = make(DNS_SETTINGS)
    r = v.verify("bob@@example.com")
    assert r.verdict is Verdict.undeliverable
    assert r.reasons == (Reason.syntax_too_many_at_signs,)
    assert r.source == "local" and r.status is Status.complete
    assert res.calls == []
    assert len(v.cache) == 0  # type: ignore[arg-type]


def test_disposable_stop() -> None:
    v, _, res = make(DNS_SETTINGS)
    r = v.verify("temp@mailinator.com")
    assert (r.verdict, r.send) == (Verdict.undeliverable, SendRecommendation.do_not_send)
    assert r.reasons == (Reason.disposable_domain,) and r.flags.disposable
    assert res.calls == []


def test_custom_domain_lists_and_allow_override() -> None:
    lists = DisposableLists(disposable=["burner.test"], allow=["ok.burner.test"])
    v = Verifier(domain_lists=lists)
    assert v.verify("a@burner.test").flags.disposable
    assert v.verify("a@sub.burner.test").flags.disposable
    assert not v.verify("a@ok.burner.test").flags.disposable


def test_strict_disposable_off_ignores_strict_list() -> None:
    lists = DisposableLists(strict=["burner.test"])
    r = Verifier(domain_lists=lists).verify("a@burner.test")
    assert not r.flags.disposable
    assert r.verdict is Verdict.unknown


def test_strict_disposable_on_flags_with_medium_confidence() -> None:
    lists = DisposableLists(disposable=["core.test"], strict=["burner.test"])
    v = Verifier(Settings(strict_disposable=True), domain_lists=lists)
    r = v.verify("a@burner.test")
    assert r.flags.disposable and r.reasons == (Reason.disposable_domain,)
    assert (r.verdict, r.send, r.confidence) == (
        Verdict.undeliverable,
        SendRecommendation.do_not_send,
        Confidence.medium,
    )
    assert v.verify("a@core.test").confidence is Confidence.high


def test_strict_disposable_default_lists_include_bundled_strict() -> None:
    assert not Verifier().verify("a@ubermail39.info").flags.disposable
    r = Verifier(Settings(strict_disposable=True)).verify("a@ubermail39.info")
    assert r.flags.disposable and r.confidence is Confidence.medium


def test_offline_flags_and_typo() -> None:
    v, _, _ = make()
    r = v.verify("info@gmail.com")
    assert r.flags.role and r.flags.free
    assert r.reasons == (Reason.role_address,)
    assert (r.verdict, r.send, r.source) == (
        Verdict.unknown,
        SendRecommendation.risky_to_send,
        "local",
    )
    t = v.verify("jane@gmal.com")
    assert t.suggestion == "jane@gmail.com"
    assert (t.verdict, t.send) == (Verdict.risky, SendRecommendation.do_not_send)
    assert Reason.possible_typo_trap in t.reasons
    g = v.verify("xkqzvwptrl@example.org")
    assert g.flags.gibberish and Reason.gibberish in g.reasons


def test_normalized_and_address_preserved() -> None:
    v, _, _ = make()
    r = v.verify("  Jane@Example.COM ")
    assert r.address == "  Jane@Example.COM "
    assert r.normalized == "Jane@example.com"


# --- dns


def test_dns_disabled_makes_no_lookups() -> None:
    v, _, res = make(Settings())
    r = v.verify("jane@example.com")
    assert res.calls == [] and r.domain is None and r.source == "local"


def test_dns_enabled_domain_found() -> None:
    v, _, res = make(DNS_SETTINGS)
    r = v.verify("jane@example.com")
    assert r.source == "dns"
    assert r.domain is not None and r.domain.mx == (MxRecord(10, "mx.example.com"),)
    assert (r.verdict, r.send) == (Verdict.unknown, SendRecommendation.risky_to_send)
    assert res.domains_queried() == ["example.com"]


def test_dns_domain_missing_and_null_mx() -> None:
    v, _, _ = make(DNS_SETTINGS)
    missing = v.verify("jane@gone.test")
    assert missing.reasons == (Reason.domain_not_found,)
    assert missing.verdict is Verdict.undeliverable
    assert v.verify("jane@nomx.test").reasons == (Reason.null_mx,)


def test_dns_timeout_is_unknown_and_not_cached() -> None:
    cache = SpyCache()
    v, rec, res = make(DNS_SETTINGS, cache=cache)
    r = v.verify("jane@slow.test")
    assert (r.verdict, r.send) == (Verdict.unknown, SendRecommendation.risky_to_send)
    assert Reason.temporary_failure in r.reasons
    assert cache.ttls == {} and len(cache) == 0
    assert len(rec.saved) == 1
    v.verify("jane@slow.test")
    assert len(res.domains_queried()) == 2  # retried, not remembered


# --- cache


def test_cache_hit_skips_resolver_and_marks_source() -> None:
    v, rec, res = make(DNS_SETTINGS)
    first = v.verify("Jane@example.com")
    calls = len(res.calls)
    second = v.verify("jane@EXAMPLE.com")
    assert len(res.calls) == calls
    assert second.source == "cache"
    assert second.address == "jane@EXAMPLE.com"
    assert second.verdict is first.verdict
    assert second.checked_at == first.checked_at
    assert len(rec.saved) == len(rec.seen) == 2


def test_cache_key_is_lowercased_normalized_address() -> None:
    cache = SpyCache()
    v, _, _ = make(DNS_SETTINGS, cache=cache)
    v.verify("Jane@Example.com")
    assert list(cache.ttls) == [KEY + "jane@example.com"]


def test_cache_entry_from_a_run_without_dns_is_ignored_when_dns_enabled() -> None:
    shared = MemoryCache()
    make(Settings(), cache=shared)[0].verify("jane@example.com")
    v, _, res = make(DNS_SETTINGS, cache=shared)
    r = v.verify("jane@example.com")
    assert r.source == "dns" and res.domains_queried() == ["example.com"]


def test_corrupt_cache_entry_is_a_miss() -> None:
    cache = MemoryCache()
    cache.set(KEY + "jane@example.com", {"nonsense": True}, 100)
    v, _, _ = make(Settings(), cache=cache)
    assert v.verify("jane@example.com").source == "local"


@pytest.mark.parametrize(
    ("address", "verdict"),
    [
        ("jane@example.com", "unknown"),
        ("jane@gone.test", "undeliverable"),
        ("jane@gmal.com", "risky"),
    ],
)
def test_ttl_by_verdict(address: str, verdict: str) -> None:
    ttls = {"deliverable": 11, "undeliverable": 22, "risky": 33, "unknown": 44, "domain": 55}
    cache = SpyCache()
    res = FakeResolver(
        {("example.com", "MX"): ["10 mx.example.com"], ("gmal.com", "MX"): ["10 mx.gmal.com"]}
    )
    v = Verifier(Settings(dns_enabled=True, cache_ttl=ttls), cache=cache, resolver=res)
    r = v.verify(address)
    assert r.verdict.value == verdict
    assert cache.ttls[KEY + r.normalized.lower()] == ttls[verdict]


def test_local_only_result_is_cached_with_its_verdict_ttl() -> None:
    cache = SpyCache()
    Verifier(cache=cache).verify("jane@example.com")
    assert cache.ttls[KEY + "jane@example.com"] == Settings().cache_ttl["unknown"]


# --- verify_many


def test_verify_many_dedupes_and_shares_dns() -> None:
    v, rec, res = make(DNS_SETTINGS)
    batch = [
        "a@example.com",
        "b@example.com",
        "A@example.com",
        "a@Example.com",
        "x@gone.test",
        "y@gone.test",
        "bad",
        "a@example.com",
    ]
    out = v.verify_many(batch)
    assert len(out) == len(batch)
    assert [r.address for r in out][:2] == ["a@example.com", "b@example.com"]
    assert out[0] is out[3] is out[7]
    assert out[6].reasons == (Reason.syntax_no_at_sign,)
    assert sorted(res.domains_queried()) == ["example.com", "gone.test"]
    unique = {r.normalized for r in out}
    assert len(unique) == 6
    assert len(rec.saved) == len(rec.seen) == 6


def test_verify_many_shares_timeouts_within_a_call() -> None:
    v, _, res = make(DNS_SETTINGS)
    out = v.verify_many(["a@slow.test", "b@slow.test"])
    assert all(Reason.temporary_failure in r.reasons for r in out)
    assert res.domains_queried() == ["slow.test"]


def test_verify_many_empty() -> None:
    assert make()[0].verify_many([]) == []


# --- callbacks


def test_callback_exceptions_propagate() -> None:
    def boom(result: Result) -> None:
        raise RuntimeError("host failure")

    with pytest.raises(RuntimeError):
        Verifier(on_result=boom).verify("jane@example.com")

    class BadStore:
        def save(self, result: Result) -> None:
            raise RuntimeError("store failure")

    with pytest.raises(RuntimeError):
        Verifier(store=BadStore()).verify("jane@example.com")


def test_store_and_callback_called_for_stops() -> None:
    v, rec, _ = make()
    v.verify("bad")
    v.verify("a@mailinator.com")
    assert len(rec.saved) == len(rec.seen) == 2


# --- smtp


def _reply() -> SmtpReply:
    return SmtpReply(250, None, "ok")


def patch_probe(
    monkeypatch: pytest.MonkeyPatch,
    outcome: ProbeResult | PendingState,
    calls: list[tuple[str, PendingState | None]] | None = None,
    reason: Reason | None = Reason.mailbox_accepted,
    reliability: str = "reliable",
) -> None:
    def fake(
        address: str,
        info: DomainInfo,
        factory: Callable[..., Any],
        settings: Settings,
        limiter: object,
        pending: PendingState | None,
    ) -> ProbeResult | PendingState:
        if calls is not None:
            calls.append((address, pending))
        return outcome

    monkeypatch.setattr(verifier_mod, "probe_mailbox", fake)
    monkeypatch.setattr(verifier_mod, "identify_provider", lambda hosts: "acme")
    monkeypatch.setattr(verifier_mod, "provider_reliability", lambda p: reliability)
    monkeypatch.setattr(
        verifier_mod, "classify_rcpt", lambda reply: (ProbeOutcome.accepted, reason)
    )


def test_smtp_disabled_never_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*a: object) -> None:
        raise AssertionError("probe must not run")

    monkeypatch.setattr(verifier_mod, "probe_mailbox", fail)
    v, _, _ = make(DNS_SETTINGS)
    assert v.verify("jane@example.com").probe is None


def test_probe_accepted_not_catch_all(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, PendingState | None]] = []
    patch_probe(
        monkeypatch,
        ProbeResult(ProbeOutcome.accepted, _reply(), catch_all=ProbeOutcome.refused),
        calls,
    )
    v, rec, _ = make(SMTP_SETTINGS)
    r = v.verify("Jane@example.com")
    assert calls == [("Jane@example.com", None)]
    assert (r.verdict, r.send, r.source) == (
        Verdict.deliverable,
        SendRecommendation.safe_to_send,
        "probe",
    )
    assert r.flags.catch_all is False and r.provider == "acme"
    assert v.verify("Jane@example.com").source == "cache" and len(calls) == 1
    assert len(rec.seen) == 2


def test_probe_catch_all(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_probe(
        monkeypatch, ProbeResult(ProbeOutcome.accepted, _reply(), catch_all=ProbeOutcome.accepted)
    )
    r = make(SMTP_SETTINGS)[0].verify("jane@example.com")
    assert r.verdict is Verdict.risky and r.flags.catch_all is True
    assert Reason.accept_all in r.reasons


def test_probe_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_probe(
        monkeypatch,
        ProbeResult(ProbeOutcome.refused, SmtpReply(550, "5.1.1", "no")),
        reason=Reason.mailbox_not_found,
    )
    r = make(SMTP_SETTINGS)[0].verify("jane@example.com")
    assert (r.verdict, r.send) == (Verdict.undeliverable, SendRecommendation.do_not_send)
    assert r.reasons == (Reason.mailbox_not_found,)


def test_probe_pending_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    state = PendingState("jane@example.com", 1, 3, 330)
    cache = SpyCache()
    patch_probe(monkeypatch, state)
    v, rec, _ = make(SMTP_SETTINGS, cache=cache)
    r = v.verify("jane@example.com")
    assert r.status is Status.pending and r.pending == state
    assert r.verdict is Verdict.unknown and Reason.greylisted in r.reasons
    assert cache.ttls == {} and len(cache) == 0
    assert len(rec.saved) == len(rec.seen) == 1


def test_resume_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    state = PendingState(
        "jane@example.com", 1, 3, 330, proxy="socks5://p", mx_host="mx.example.com"
    )
    calls: list[tuple[str, PendingState | None]] = []
    patch_probe(monkeypatch, state, calls)
    v, _, _ = make(SMTP_SETTINGS)
    first = v.verify("jane@example.com")
    assert first.pending is not None
    token = first.pending.to_token()

    patch_probe(
        monkeypatch,
        ProbeResult(ProbeOutcome.accepted, _reply(), catch_all=ProbeOutcome.refused),
        calls,
    )
    final = v.verify("jane@example.com", resume_token=token)
    assert calls[-1] == ("jane@example.com", state)
    assert final.status is Status.complete and final.verdict is Verdict.deliverable


def test_resume_skips_cache_read(monkeypatch: pytest.MonkeyPatch) -> None:
    v, _, _ = make(SMTP_SETTINGS)
    patch_probe(monkeypatch, ProbeResult(ProbeOutcome.accepted, _reply(), ProbeOutcome.refused))
    v.verify("jane@example.com")
    calls: list[tuple[str, PendingState | None]] = []
    patch_probe(
        monkeypatch, ProbeResult(ProbeOutcome.accepted, _reply(), ProbeOutcome.refused), calls
    )
    token = PendingState("jane@example.com", 1, 3, 330).to_token()
    assert v.verify("jane@example.com", resume_token=token).source == "probe"
    assert len(calls) == 1


def test_bad_resume_tokens() -> None:
    v, _, _ = make(SMTP_SETTINGS)
    with pytest.raises(PrebounceError):
        v.verify("jane@example.com", resume_token="garbage")
    other = PendingState("other@example.com", 1, 3, 330).to_token()
    with pytest.raises(PrebounceError):
        v.verify("jane@example.com", resume_token=other)


def test_probe_not_implemented_propagates() -> None:
    v, _, _ = make(SMTP_SETTINGS)
    with pytest.raises(NotImplementedError):
        v.verify("jane@example.com")


@pytest.mark.parametrize(
    "address", ["jane@gmal.com", "jane@gone.test", "jane@nomx.test", "bad", "a@mailinator.com"]
)
def test_probe_skipped_when_earlier_stage_decides(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    calls: list[tuple[str, PendingState | None]] = []
    patch_probe(monkeypatch, ProbeResult(ProbeOutcome.accepted, _reply()), calls)
    res = FakeResolver({("gmal.com", "MX"): ["10 mx.gmal.com"], ("nomx.test", "MX"): ["0 ."]})
    v = Verifier(SMTP_SETTINGS, resolver=res)
    v.verify(address)
    assert calls == []


# --- module level


def test_module_verify_uses_lazy_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verifier_mod, "_default_verifier", None)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: Settings()))
    r = verifier_mod.verify("temp@mailinator.com")
    assert r.verdict is Verdict.undeliverable
    first = verifier_mod._default_verifier
    assert first is not None
    verifier_mod.verify("jane@example.com")
    assert verifier_mod._default_verifier is first


def test_default_resolver_used_when_none_injected(monkeypatch: pytest.MonkeyPatch) -> None:
    res = resolver()
    monkeypatch.setattr(verifier_mod, "default_resolver", lambda: res)
    Verifier(DNS_SETTINGS).verify("jane@example.com")
    assert res.domains_queried() == ["example.com"]


# --- syntax vs email-validator

# Documented intentional differences, excluded from the comparison: bracketed IP-literal domains
# (email-validator accepts them only with allow_domain_literal; check_syntax rejects them).
SYNTAX_SAMPLES = [
    "jane@example.com",
    "jane.doe@example.com",
    "jane+tag@example.com",
    "o'brien@example.com",
    "user_name@sub.example.co.uk",
    "a@b.co",
    "JANE@EXAMPLE.COM",
    "jane@xn--nxasmq6b.com",
    "jürgen@example.de",
    "jane@münchen.de",
    "plainaddress",
    "@example.com",
    "jane@",
    "jane@@example.com",
    "jane@example",
    "jane@.example.com",
    "jane@example..com",
    ".jane@example.com",
    "jane.@example.com",
    "ja..ne@example.com",
    "jane doe@example.com",
    "jane@exa mple.com",
    "jane@-example.com",
    "jane@example-.com",
    "jane@" + "a" * 64 + ".com",
    "jane,doe@example.com",
    "<jane@example.com>",
    "jane@example.com.",
    "",
]

LONG_LOCAL = "a" * 65 + "@example.com"
IP_LITERAL_EXCLUDED = ["jane@[192.168.0.1]", "jane@[IPv6:2001:db8::1]"]


def test_syntax_agrees_with_email_validator() -> None:
    ev = pytest.importorskip("email_validator")

    def reference(addr: str) -> bool:
        try:
            ev.validate_email(addr, check_deliverability=False)
        except ev.EmailNotValidError:
            return False
        return True

    disagreements = [
        a for a in SYNTAX_SAMPLES if (address_mod.check_syntax(a) == ()) != reference(a)
    ]
    assert disagreements == []
    # Intentional: check_syntax enforces the RFC 5321 64-octet local-part limit, which
    # email-validator 2.3 does not.
    assert Reason.syntax_local_too_long in address_mod.check_syntax(LONG_LOCAL)
    for a in IP_LITERAL_EXCLUDED:
        assert address_mod.check_syntax(a) != ()
