"""Configuration. Defaults are all-safe: no network access of any kind."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from prebounce.errors import ConfigurationError

_DAY = 86400


def _default_cache_ttl() -> dict[str, int]:
    return {
        "deliverable": 30 * _DAY,
        "undeliverable": 30 * _DAY,
        "risky": 7 * _DAY,
        "unknown": 1 * _DAY,
        "domain": 1 * _DAY,
    }


@dataclass(frozen=True)
class ProxyConfig:
    """A SOCKS5 proxy with the identity used when probing through it."""

    url: str
    helo: str
    mail_from: str
    providers: tuple[str, ...] = ()  # provider ids this proxy is preferred for; empty = any


@dataclass(frozen=True)
class Settings:
    dns_enabled: bool = False
    smtp_enabled: bool = False
    smtp_helo: str | None = None
    smtp_mail_from: str | None = None
    smtp_proxies: tuple[ProxyConfig, ...] = ()
    probe_timeout: float = 15.0
    catch_all_check: bool = True
    max_greylist_attempts: int = 3
    greylist_delay_seconds: int = 330
    blocklist_zones: tuple[str, ...] = ()
    cache_ttl: dict[str, int] = field(default_factory=_default_cache_ttl)
    strict_disposable: bool = False

    def __post_init__(self) -> None:
        if self.smtp_enabled:
            if not self.dns_enabled:
                raise ConfigurationError("smtp_enabled requires dns_enabled")
            direct = bool(self.smtp_helo and self.smtp_mail_from)
            if not direct and not self.smtp_proxies:
                raise ConfigurationError(
                    "smtp_enabled requires smtp_helo and smtp_mail_from, or smtp_proxies"
                )
        if self.blocklist_zones and not self.dns_enabled:
            raise ConfigurationError("blocklist_zones requires dns_enabled")
        if self.probe_timeout <= 0:
            raise ConfigurationError("probe_timeout must be positive")
        if self.max_greylist_attempts < 1:
            raise ConfigurationError("max_greylist_attempts must be at least 1")
        if self.greylist_delay_seconds < 0:
            raise ConfigurationError("greylist_delay_seconds must not be negative")
        for name, ttl in self.cache_ttl.items():
            if ttl < 0:
                raise ConfigurationError(f"cache_ttl[{name!r}] must not be negative")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, prefix: str = "PREBOUNCE_") -> Settings:
        """Build Settings from environment variables, e.g. PREBOUNCE_DNS_ENABLED=true.

        Variables: DNS_ENABLED, SMTP_ENABLED, SMTP_HELO, SMTP_MAIL_FROM, SMTP_PROXIES (JSON list of
        {"url","helo","mail_from","providers"}), PROBE_TIMEOUT, CATCH_ALL_CHECK,
        MAX_GREYLIST_ATTEMPTS, GREYLIST_DELAY_SECONDS, BLOCKLIST_ZONES (comma separated),
        CACHE_TTL (JSON object merged over the defaults), STRICT_DISPOSABLE.
        """
        source = os.environ if env is None else env

        def raw(name: str) -> str | None:
            value = source.get(prefix + name)
            return value if value is not None and value.strip() != "" else None

        kwargs: dict[str, Any] = {}
        for name in ("DNS_ENABLED", "SMTP_ENABLED", "CATCH_ALL_CHECK", "STRICT_DISPOSABLE"):
            value = raw(name)
            if value is not None:
                kwargs[name.lower()] = _parse_bool(prefix + name, value)
        for name in ("MAX_GREYLIST_ATTEMPTS", "GREYLIST_DELAY_SECONDS"):
            value = raw(name)
            if value is not None:
                kwargs[name.lower()] = _parse_int(prefix + name, value)
        value = raw("PROBE_TIMEOUT")
        if value is not None:
            try:
                kwargs["probe_timeout"] = float(value)
            except ValueError:
                raise ConfigurationError(f"{prefix}PROBE_TIMEOUT: not a number") from None
        for name in ("SMTP_HELO", "SMTP_MAIL_FROM"):
            value = raw(name)
            if value is not None:
                kwargs[name.lower()] = value.strip()
        value = raw("BLOCKLIST_ZONES")
        if value is not None:
            kwargs["blocklist_zones"] = tuple(z.strip() for z in value.split(",") if z.strip())
        value = raw("SMTP_PROXIES")
        if value is not None:
            kwargs["smtp_proxies"] = _parse_proxies(prefix + "SMTP_PROXIES", value)
        value = raw("CACHE_TTL")
        if value is not None:
            kwargs["cache_ttl"] = _parse_ttl(prefix + "CACHE_TTL", value)
        return cls(**kwargs)


def _parse_bool(name: str, value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name}: not a boolean: {value!r}")


def _parse_int(name: str, value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        raise ConfigurationError(f"{name}: not an integer: {value!r}") from None


def _load_json(name: str, value: str) -> Any:
    try:
        return json.loads(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name}: invalid JSON: {exc}") from None


def _parse_proxies(name: str, value: str) -> tuple[ProxyConfig, ...]:
    data = _load_json(name, value)
    if not isinstance(data, list):
        raise ConfigurationError(f"{name}: expected a JSON list")
    proxies: list[ProxyConfig] = []
    for item in data:
        if not isinstance(item, dict):
            raise ConfigurationError(f"{name}: each proxy must be an object")
        try:
            proxies.append(
                ProxyConfig(
                    url=str(item["url"]),
                    helo=str(item["helo"]),
                    mail_from=str(item["mail_from"]),
                    providers=tuple(str(p) for p in item.get("providers", ())),
                )
            )
        except KeyError as exc:
            raise ConfigurationError(f"{name}: proxy is missing {exc.args[0]!r}") from None
    return tuple(proxies)


def _parse_ttl(name: str, value: str) -> dict[str, int]:
    data = _load_json(name, value)
    if not isinstance(data, dict):
        raise ConfigurationError(f"{name}: expected a JSON object")
    ttl = _default_cache_ttl()
    for key, seconds in data.items():
        if key not in ttl:
            raise ConfigurationError(f"{name}: unknown key {key!r}")
        if not isinstance(seconds, int) or isinstance(seconds, bool):
            raise ConfigurationError(f"{name}: {key!r} must be an integer")
        ttl[key] = seconds
    return ttl
