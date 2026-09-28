"""Core result types. All are immutable and JSON round-trippable via to_dict/from_dict."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from prebounce.errors import PrebounceError


class Verdict(str, Enum):
    deliverable = "deliverable"
    undeliverable = "undeliverable"
    risky = "risky"
    unknown = "unknown"


class SendRecommendation(str, Enum):
    safe_to_send = "safe_to_send"
    risky_to_send = "risky_to_send"
    do_not_send = "do_not_send"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Status(str, Enum):
    complete = "complete"
    pending = "pending"


class Reason(str, Enum):
    """Canonical machine-readable reason codes used everywhere."""

    syntax_invalid = "syntax_invalid"
    syntax_too_many_at_signs = "syntax_too_many_at_signs"
    syntax_no_at_sign = "syntax_no_at_sign"
    syntax_local_too_long = "syntax_local_too_long"
    syntax_address_too_long = "syntax_address_too_long"
    syntax_domain_invalid = "syntax_domain_invalid"
    disposable_domain = "disposable_domain"
    role_address = "role_address"
    free_provider = "free_provider"
    typo_domain = "typo_domain"
    gibberish = "gibberish"
    domain_not_found = "domain_not_found"
    no_mx = "no_mx"
    null_mx = "null_mx"
    domain_blocklisted = "domain_blocklisted"
    mailbox_accepted = "mailbox_accepted"
    mailbox_not_found = "mailbox_not_found"
    mailbox_full = "mailbox_full"
    mailbox_disabled = "mailbox_disabled"
    accept_all = "accept_all"
    security_gateway = "security_gateway"
    greylisted = "greylisted"
    temporary_failure = "temporary_failure"
    prober_blocked = "prober_blocked"
    provider_unreliable = "provider_unreliable"
    connection_failed = "connection_failed"
    probe_skipped = "probe_skipped"
    possible_typo_trap = "possible_typo_trap"
    recently_registered_domain = "recently_registered_domain"


class ProbeOutcome(str, Enum):
    accepted = "accepted"
    refused = "refused"
    inconclusive = "inconclusive"
    not_run = "not_run"


@dataclass(frozen=True)
class SmtpReply:
    code: int
    enhanced: str | None
    text: str

    @property
    def is_positive(self) -> bool:
        return 200 <= self.code < 400

    @property
    def is_transient(self) -> bool:
        return 400 <= self.code < 500

    @property
    def is_permanent(self) -> bool:
        return 500 <= self.code < 600

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "enhanced": self.enhanced, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmtpReply:
        return cls(code=int(data["code"]), enhanced=data.get("enhanced"), text=str(data["text"]))


@dataclass(frozen=True)
class ProbeResult:
    outcome: ProbeOutcome
    reply: SmtpReply | None = None
    catch_all: ProbeOutcome = ProbeOutcome.not_run
    mx_host: str | None = None
    proxy: str | None = None
    transcript: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "reply": self.reply.to_dict() if self.reply else None,
            "catch_all": self.catch_all.value,
            "mx_host": self.mx_host,
            "proxy": self.proxy,
            "transcript": list(self.transcript),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProbeResult:
        reply = data.get("reply")
        return cls(
            outcome=ProbeOutcome(data["outcome"]),
            reply=SmtpReply.from_dict(reply) if reply else None,
            catch_all=ProbeOutcome(data.get("catch_all", "not_run")),
            mx_host=data.get("mx_host"),
            proxy=data.get("proxy"),
            transcript=tuple(data.get("transcript", ())),
        )


@dataclass(frozen=True)
class Flags:
    free: bool = False
    role: bool = False
    disposable: bool = False
    catch_all: bool | None = None
    gibberish: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "free": self.free,
            "role": self.role,
            "disposable": self.disposable,
            "catch_all": self.catch_all,
            "gibberish": self.gibberish,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Flags:
        return cls(
            free=bool(data.get("free", False)),
            role=bool(data.get("role", False)),
            disposable=bool(data.get("disposable", False)),
            catch_all=data.get("catch_all"),
            gibberish=bool(data.get("gibberish", False)),
        )


@dataclass(frozen=True)
class MxRecord:
    preference: int
    host: str


@dataclass(frozen=True)
class DomainInfo:
    domain: str
    exists: bool
    mx: tuple[MxRecord, ...] = ()
    null_mx: bool = False
    implicit_mx: bool = False
    blocklisted: tuple[str, ...] = ()
    provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "exists": self.exists,
            "mx": [[m.preference, m.host] for m in self.mx],
            "null_mx": self.null_mx,
            "implicit_mx": self.implicit_mx,
            "blocklisted": list(self.blocklisted),
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainInfo:
        return cls(
            domain=str(data["domain"]),
            exists=bool(data["exists"]),
            mx=tuple(MxRecord(int(p), str(h)) for p, h in data.get("mx", ())),
            null_mx=bool(data.get("null_mx", False)),
            implicit_mx=bool(data.get("implicit_mx", False)),
            blocklisted=tuple(data.get("blocklisted", ())),
            provider=data.get("provider"),
        )


_TOKEN_VERSION = "v1"


@dataclass(frozen=True)
class PendingState:
    """Opaque resume state for a greylisted address; round-trips through a token string."""

    address: str
    attempt: int
    max_attempts: int
    retry_after_seconds: int
    proxy: str | None = None
    mx_host: str | None = None

    def to_token(self) -> str:
        payload = {
            "address": self.address,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "retry_after_seconds": self.retry_after_seconds,
            "proxy": self.proxy,
            "mx_host": self.mx_host,
        }
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        return f"{_TOKEN_VERSION}.{body}"

    @classmethod
    def from_token(cls, token: str) -> PendingState:
        """Raise PrebounceError if the token is malformed or has an unknown version."""
        version, sep, body = token.partition(".")
        if not sep or version != _TOKEN_VERSION:
            raise PrebounceError("unsupported resume token version")
        try:
            data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            return cls(
                address=str(data["address"]),
                attempt=int(data["attempt"]),
                max_attempts=int(data["max_attempts"]),
                retry_after_seconds=int(data["retry_after_seconds"]),
                proxy=data.get("proxy"),
                mx_host=data.get("mx_host"),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise PrebounceError("malformed resume token") from exc


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Result:
    address: str
    normalized: str
    status: Status
    verdict: Verdict
    send: SendRecommendation
    confidence: Confidence
    reasons: tuple[Reason, ...] = ()
    flags: Flags = field(default_factory=Flags)
    suggestion: str | None = None
    domain: DomainInfo | None = None
    probe: ProbeResult | None = None
    provider: str | None = None
    source: str = "local"  # "local" | "dns" | "probe" | "cache"
    pending: PendingState | None = None
    checked_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "normalized": self.normalized,
            "status": self.status.value,
            "verdict": self.verdict.value,
            "send": self.send.value,
            "confidence": self.confidence.value,
            "reasons": [r.value for r in self.reasons],
            "flags": self.flags.to_dict(),
            "suggestion": self.suggestion,
            "domain": self.domain.to_dict() if self.domain else None,
            "probe": self.probe.to_dict() if self.probe else None,
            "provider": self.provider,
            "source": self.source,
            "pending": self.pending.to_token() if self.pending else None,
            "checked_at": self.checked_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Result:
        checked_at = datetime.fromisoformat(data["checked_at"])
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        domain = data.get("domain")
        probe = data.get("probe")
        pending = data.get("pending")
        return cls(
            address=str(data["address"]),
            normalized=str(data["normalized"]),
            status=Status(data["status"]),
            verdict=Verdict(data["verdict"]),
            send=SendRecommendation(data["send"]),
            confidence=Confidence(data["confidence"]),
            reasons=tuple(Reason(r) for r in data.get("reasons", ())),
            flags=Flags.from_dict(data.get("flags", {})),
            suggestion=data.get("suggestion"),
            domain=DomainInfo.from_dict(domain) if domain else None,
            probe=ProbeResult.from_dict(probe) if probe else None,
            provider=data.get("provider"),
            source=str(data.get("source", "local")),
            pending=PendingState.from_token(pending) if pending else None,
            checked_at=checked_at,
        )
