"""DNS: domain existence, MX discovery and blocklist lookups."""

from __future__ import annotations

import ipaddress
from typing import Any

from prebounce.errors import (
    ConfigurationError,
    DNSTimeout,
    NoAnswer,
    NXDomain,
)
from prebounce.protocols import Resolver
from prebounce.settings import Settings
from prebounce.types import DomainInfo, MxRecord

_DEFAULT_TIMEOUT = 5.0
_LISTED_NET = ipaddress.ip_network("127.0.1.0/24")
_ERROR_NET = ipaddress.ip_network("127.255.255.0/24")
_LOOPBACK_NET = ipaddress.ip_network("127.0.0.0/8")


def lookup_domain(domain: str, resolver: Resolver, settings: Settings) -> DomainInfo:
    """Resolve MX (falling back to implicit A/AAAA MX), detect null MX and query blocklist_zones.

    A missing domain returns DomainInfo(exists=False). DNSTimeout raised by any MX, A or AAAA
    lookup propagates to the caller, so a timeout is never reported as "domain not found".
    A timeout on a single blocklist zone is treated as "not listed" for that zone.

    RFC 7505: a lone MX of preference 0 and host "." is a null MX (null_mx=True, no mx).
    RFC 5321 section 5.1: with no MX records but an A or AAAA record, the domain itself is the
    implicit MX (implicit_mx=True).
    """
    name = domain.strip().rstrip(".").lower()
    try:
        raw_mx = resolver.resolve(name, "MX")
    except NXDomain:
        return DomainInfo(domain=name, exists=False)
    except NoAnswer:
        raw_mx = []

    mx: tuple[MxRecord, ...] = ()
    null_mx = False
    implicit_mx = False
    if raw_mx:
        parsed = _parse_mx(raw_mx)
        if len(parsed) == 1 and parsed[0] == (0, ""):
            null_mx = True
        else:
            mx = tuple(MxRecord(pref, host) for pref, host in sorted({p for p in parsed if p[1]}))
    else:
        implicit_mx = _has_address(name, resolver)
        if implicit_mx:
            mx = (MxRecord(0, name),)

    return DomainInfo(
        domain=name,
        exists=True,
        mx=mx,
        null_mx=null_mx,
        implicit_mx=implicit_mx,
        blocklisted=_blocklisted(name, resolver, settings),
    )


def _parse_mx(records: list[str]) -> list[tuple[int, str]]:
    parsed: list[tuple[int, str]] = []
    for record in records:
        parts = record.split()
        if len(parts) != 2:
            continue
        try:
            pref = int(parts[0])
        except ValueError:
            continue
        parsed.append((pref, parts[1].rstrip(".").lower()))
    return parsed


def _has_address(name: str, resolver: Resolver) -> bool:
    for rdtype in ("A", "AAAA"):
        try:
            if resolver.resolve(name, rdtype):
                return True
        except (NoAnswer, NXDomain):
            continue
    return False


def _blocklisted(name: str, resolver: Resolver, settings: Settings) -> tuple[str, ...]:
    listed: list[str] = []
    for zone in settings.blocklist_zones:
        try:
            answers = resolver.resolve(f"{name}.{zone}", "A")
        except (NXDomain, NoAnswer, DNSTimeout):
            continue
        if any(_is_listing(answer) for answer in answers):
            listed.append(zone)
    return tuple(listed)


def _is_listing(answer: str) -> bool:
    """127.255.255.x are Spamhaus error codes (refused/excessive use), not listings."""
    try:
        addr = ipaddress.ip_address(answer.strip())
    except ValueError:
        return False
    if addr.version != 4 or addr not in _LOOPBACK_NET:
        return False
    return addr not in _ERROR_NET


class _DnsPythonResolver:
    """Adapts a dnspython resolver to the Resolver protocol."""

    def __init__(self, backend: Any, dns_exceptions: Any) -> None:
        self._backend = backend
        self._exc = dns_exceptions

    def resolve(self, name: str, rdtype: str) -> list[str]:
        exc = self._exc
        try:
            answer = self._backend.resolve(name, rdtype)
        except exc.NXDOMAIN as err:
            raise NXDomain(name) from err
        except (exc.NoAnswer, exc.NoNameservers) as err:
            raise NoAnswer(name) from err
        except exc.Timeout as err:  # LifetimeTimeout subclasses Timeout
            raise DNSTimeout(name) from err
        if rdtype == "MX":
            return [f"{r.preference} {r.exchange.to_text().rstrip('.')}" for r in answer]
        return [r.to_text() for r in answer]


def default_resolver() -> Resolver:
    """Return a dnspython-backed Resolver. Raises ConfigurationError if dnspython is missing."""
    try:
        import dns.exception
        import dns.resolver
    except ImportError as exc:
        raise ConfigurationError(
            "dnspython is required for DNS lookups: pip install prebounce[dns]"
        ) from exc
    backend = dns.resolver.Resolver()
    backend.timeout = _DEFAULT_TIMEOUT
    backend.lifetime = _DEFAULT_TIMEOUT
    return _DnsPythonResolver(backend, _ExcNamespace(dns.resolver, dns.exception))


class _ExcNamespace:
    """Groups the dnspython exception classes the adapter maps."""

    def __init__(self, resolver_mod: Any, exception_mod: Any) -> None:
        self.NXDOMAIN = resolver_mod.NXDOMAIN
        self.NoAnswer = resolver_mod.NoAnswer
        self.NoNameservers = resolver_mod.NoNameservers
        self.Timeout = exception_mod.Timeout
