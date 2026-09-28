"""DNS lookups against a dict-driven fake resolver; no network.

Cases follow RFC 7505 (null MX), RFC 5321 section 5.1 (implicit MX), Spamhaus DBL return codes
and the scenarios in python-email-validator's deliverability tests (missing domain, null MX,
IPv6-only fallback, TXT-only domain).
"""

from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace
from typing import Any

import dns.exception
import dns.resolver
import pytest

from prebounce import dns as dns_mod
from prebounce.dns import default_resolver, lookup_domain
from prebounce.errors import ConfigurationError, DNSTimeout, NoAnswer, NXDomain
from prebounce.settings import Settings


class FakeResolver:
    def __init__(self, records: dict[tuple[str, str], list[str] | Exception]) -> None:
        self.records = records
        self.calls: list[tuple[str, str]] = []

    def resolve(self, name: str, rdtype: str) -> list[str]:
        self.calls.append((name, rdtype))
        result = self.records.get((name, rdtype), NoAnswer(name))
        if isinstance(result, Exception):
            raise result
        return result


SETTINGS = Settings(dns_enabled=True)


def lookup(
    records: dict[tuple[str, str], list[str] | Exception], domain: str = "example.org"
) -> Any:
    return lookup_domain(domain, FakeResolver(records), SETTINGS)


def test_mx_sorted_by_preference_then_host_and_deduped() -> None:
    info = lookup(
        {
            ("example.org", "MX"): [
                "20 mx2.example.org",
                "10 b.example.org",
                "10 a.example.org",
                "10 a.example.org",
            ]
        }
    )
    assert info.exists
    assert [(m.preference, m.host) for m in info.mx] == [
        (10, "a.example.org"),
        (10, "b.example.org"),
        (20, "mx2.example.org"),
    ]
    assert not info.null_mx and not info.implicit_mx


def test_trailing_dots_and_case_normalised() -> None:
    info = lookup(
        {("example.org", "MX"): ["10 MX.Example.ORG.", "10 mx.example.org"]}, "Example.ORG."
    )
    assert info.domain == "example.org"
    assert [(m.preference, m.host) for m in info.mx] == [(10, "mx.example.org")]


def test_malformed_mx_records_ignored() -> None:
    info = lookup({("example.org", "MX"): ["garbage", "x host.example.org", "5 ok.example.org"]})
    assert [m.host for m in info.mx] == ["ok.example.org"]


def test_null_mx() -> None:
    info = lookup({("example.org", "MX"): ["0 ."]})
    assert info.exists and info.null_mx and info.mx == () and not info.implicit_mx


def test_dot_host_among_real_mx_is_ignored() -> None:
    info = lookup({("example.org", "MX"): ["0 .", "10 mx.example.org"]})
    assert not info.null_mx
    assert [m.host for m in info.mx] == ["mx.example.org"]


def test_null_mx_requires_preference_zero() -> None:
    info = lookup({("example.org", "MX"): ["10 ."]})
    assert not info.null_mx and info.mx == ()


def test_implicit_mx_via_a() -> None:
    info = lookup({("example.org", "A"): ["192.0.2.1"]})
    assert info.exists and info.implicit_mx
    assert [(m.preference, m.host) for m in info.mx] == [(0, "example.org")]


def test_implicit_mx_via_aaaa_only() -> None:
    info = lookup({("example.org", "AAAA"): ["2001:db8::1"]})
    assert info.implicit_mx
    assert [m.host for m in info.mx] == ["example.org"]


def test_explicit_mx_skips_address_lookups() -> None:
    resolver = FakeResolver({("example.org", "MX"): ["10 mx.example.org"]})
    lookup_domain("example.org", resolver, SETTINGS)
    assert resolver.calls == [("example.org", "MX")]


def test_nxdomain() -> None:
    info = lookup({("example.org", "MX"): NXDomain("example.org")})
    assert not info.exists and info.mx == () and info.blocklisted == ()


def test_no_records_at_all_domain_exists() -> None:
    info = lookup({("example.org", "TXT"): ["v=spf1 -all"]})
    assert info.exists and info.mx == () and not info.implicit_mx and not info.null_mx


@pytest.mark.parametrize("rdtype", ["MX", "A", "AAAA"])
def test_timeout_propagates(rdtype: str) -> None:
    records: dict[tuple[str, str], list[str] | Exception] = {
        ("example.org", rdtype): DNSTimeout("example.org")
    }
    with pytest.raises(DNSTimeout):
        lookup(records)


def blocklist_lookup(answer: list[str] | Exception) -> Any:
    settings = Settings(dns_enabled=True, blocklist_zones=("dbl.spamhaus.org", "other.example"))
    resolver = FakeResolver(
        {
            ("example.org", "MX"): ["10 mx.example.org"],
            ("example.org.dbl.spamhaus.org", "A"): answer,
        }
    )
    return lookup_domain("example.org", resolver, settings)


@pytest.mark.parametrize("code", ["127.0.1.2", "127.0.1.4", "127.0.1.255", "127.0.0.2"])
def test_blocklist_listed(code: str) -> None:
    assert blocklist_lookup([code]).blocklisted == ("dbl.spamhaus.org",)


@pytest.mark.parametrize("code", ["127.255.255.252", "127.255.255.254", "127.255.255.255"])
def test_blocklist_error_codes_not_listed(code: str) -> None:
    assert blocklist_lookup([code]).blocklisted == ()


def test_blocklist_error_code_mixed_with_listing_is_listed() -> None:
    assert blocklist_lookup(["127.255.255.254", "127.0.1.2"]).blocklisted == ("dbl.spamhaus.org",)


def test_blocklist_nxdomain_not_listed() -> None:
    assert blocklist_lookup(NXDomain("x")).blocklisted == ()


def test_blocklist_non_loopback_answer_not_listed() -> None:
    assert blocklist_lookup(["192.0.2.1", "not-an-ip"]).blocklisted == ()


def test_blocklist_timeout_not_listed() -> None:
    assert blocklist_lookup(DNSTimeout("x")).blocklisted == ()


def test_blocklist_zones_not_queried_when_domain_missing() -> None:
    settings = Settings(dns_enabled=True, blocklist_zones=("dbl.spamhaus.org",))
    resolver = FakeResolver({("example.org", "MX"): NXDomain("example.org")})
    lookup_domain("example.org", resolver, settings)
    assert resolver.calls == [("example.org", "MX")]


def test_no_zones_no_blocklist_queries() -> None:
    resolver = FakeResolver({("example.org", "MX"): ["10 mx.example.org"]})
    assert lookup_domain("example.org", resolver, SETTINGS).blocklisted == ()
    assert len(resolver.calls) == 1


# Adapter


class FakeBackend:
    def __init__(self, result: Any) -> None:
        self.result = result

    def resolve(self, name: str, rdtype: str) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def adapter(result: Any) -> Any:
    exc = dns_mod._ExcNamespace(dns.resolver, dns.exception)
    return dns_mod._DnsPythonResolver(FakeBackend(result), exc)


def test_adapter_formats_mx_and_strips_dot() -> None:
    mx = SimpleNamespace(preference=10, exchange=SimpleNamespace(to_text=lambda: "mx.example.org."))
    assert adapter([mx]).resolve("example.org", "MX") == ["10 mx.example.org"]


def test_adapter_formats_other_types() -> None:
    a = SimpleNamespace(to_text=lambda: "192.0.2.1")
    assert adapter([a]).resolve("example.org", "A") == ["192.0.2.1"]


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (dns.resolver.NXDOMAIN(), NXDomain),
        (dns.resolver.NoAnswer(), NoAnswer),
        (dns.resolver.NoNameservers(), NoAnswer),
        (dns.resolver.LifetimeTimeout(), DNSTimeout),
        (dns.exception.Timeout(), DNSTimeout),
    ],
)
def test_adapter_maps_exceptions(raised: Exception, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        adapter(raised).resolve("example.org", "MX")


def test_default_resolver_builds_adapter_with_timeouts() -> None:
    resolver = default_resolver()
    assert isinstance(resolver, dns_mod._DnsPythonResolver)
    assert resolver._backend.timeout == 5.0
    assert resolver._backend.lifetime == 5.0


def test_default_resolver_without_dnspython(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "dns" or name.startswith("dns."):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    for mod in [m for m in sys.modules if m == "dns" or m.startswith("dns.")]:
        monkeypatch.delitem(sys.modules, mod)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ConfigurationError, match=r"prebounce\[dns\]"):
        default_resolver()
