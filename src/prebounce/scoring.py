"""Turns collected evidence into a verdict, recommendation, confidence and reasons."""

from __future__ import annotations

from prebounce.types import (
    Confidence,
    DomainInfo,
    Flags,
    ProbeOutcome,
    ProbeResult,
    Reason,
    SendRecommendation,
    Verdict,
)

Scored = tuple[Verdict, SendRecommendation, Confidence, tuple[Reason, ...]]

_DO_NOT_SEND = SendRecommendation.do_not_send
_RISKY = SendRecommendation.risky_to_send
_SAFE = SendRecommendation.safe_to_send


def _dedupe(reasons: list[Reason]) -> tuple[Reason, ...]:
    return tuple(dict.fromkeys(reasons))


def _flag_reasons(flags: Flags) -> list[Reason]:
    reasons: list[Reason] = []
    if flags.role:
        reasons.append(Reason.role_address)
    if flags.gibberish:
        reasons.append(Reason.gibberish)
    return reasons


def _domain_reasons(domain: DomainInfo) -> list[Reason]:
    if not domain.exists:
        return [Reason.domain_not_found]
    if domain.null_mx:
        return [Reason.null_mx]
    if not domain.mx:
        return [Reason.no_mx]
    return []


def _with_flags(
    verdict: Verdict,
    send: SendRecommendation,
    confidence: Confidence,
    reasons: list[Reason],
    flags: Flags,
) -> Scored:
    """Append role/gibberish reasons; they only lower a safe recommendation to risky."""
    reasons = reasons + _flag_reasons(flags)
    if send is _SAFE and (flags.role or flags.gibberish):
        send = _RISKY
    return verdict, send, confidence, _dedupe(reasons)


def _probed(
    probe: ProbeResult,
    flags: Flags,
    probe_reason: Reason | None,
    provider_reliability: str | None,
) -> Scored:
    if probe.outcome is ProbeOutcome.refused:
        if probe_reason is Reason.mailbox_full:
            return _with_flags(Verdict.risky, _RISKY, Confidence.medium, [probe_reason], flags)
        reason: Reason = (
            probe_reason
            if probe_reason in (Reason.mailbox_not_found, Reason.mailbox_disabled)
            else Reason.mailbox_not_found
        )
        return _with_flags(Verdict.undeliverable, _DO_NOT_SEND, Confidence.high, [reason], flags)

    if probe.outcome is ProbeOutcome.accepted:
        if provider_reliability == "unreliable":
            reasons = [Reason.provider_unreliable]
            return _with_flags(Verdict.unknown, _RISKY, Confidence.low, reasons, flags)
        if probe.catch_all is ProbeOutcome.accepted:
            reasons = [Reason.mailbox_accepted, Reason.accept_all]
            return _with_flags(Verdict.risky, _RISKY, Confidence.low, reasons, flags)
        if provider_reliability == "accept_all_gateway":
            reasons = [Reason.mailbox_accepted, Reason.security_gateway, Reason.accept_all]
            return _with_flags(Verdict.risky, _RISKY, Confidence.low, reasons, flags)
        if probe.catch_all is ProbeOutcome.refused:
            reasons = [Reason.mailbox_accepted]
            return _with_flags(Verdict.deliverable, _SAFE, Confidence.high, reasons, flags)
        reasons = [Reason.mailbox_accepted]
        return _with_flags(Verdict.deliverable, _RISKY, Confidence.medium, reasons, flags)

    # inconclusive: never undeliverable
    unclear: Reason
    if probe_reason is not None:
        unclear = probe_reason
    elif probe.reply is None:
        unclear = Reason.connection_failed
    else:
        unclear = Reason.temporary_failure
    reasons = [unclear]
    if provider_reliability == "unreliable":
        reasons.append(Reason.provider_unreliable)
    return _with_flags(Verdict.unknown, _RISKY, Confidence.low, reasons, flags)


def score(
    syntax: tuple[Reason, ...],
    flags: Flags,
    domain: DomainInfo | None,
    probe: ProbeResult | None,
    probe_reason: Reason | None,
    provider_reliability: str | None,
    suggestion: str | None,
    strict_match: bool = False,
) -> tuple[Verdict, SendRecommendation, Confidence, tuple[Reason, ...]]:
    """Combine evidence. Pure function.

    probe_reason is the second value of smtp.replies.classify_rcpt; provider_reliability is one of
    "reliable", "unreliable", "accept_all_gateway" or None. A blocked or failed probe never yields
    undeliverable.

    Precedence: syntax, disposable, domain lookup, blocklist, typo, probe, then the no-probe
    fallback. Role and gibberish flags add reasons and lower safe_to_send to risky_to_send.
    A disposable domain is always undeliverable. strict_match means only the opt-in strict list
    flagged it; that list has more false positives, so confidence drops to medium.
    """
    if syntax:
        return Verdict.undeliverable, _DO_NOT_SEND, Confidence.high, _dedupe(list(syntax))
    if flags.disposable:
        return (
            Verdict.undeliverable,
            _DO_NOT_SEND,
            Confidence.medium if strict_match else Confidence.high,
            (Reason.disposable_domain,),
        )
    if domain is not None:
        domain_reasons = _domain_reasons(domain)
        if domain_reasons:
            return Verdict.undeliverable, _DO_NOT_SEND, Confidence.high, tuple(domain_reasons)
        if domain.blocklisted:
            return _with_flags(
                Verdict.risky, _DO_NOT_SEND, Confidence.medium, [Reason.domain_blocklisted], flags
            )
    if suggestion is not None:
        reasons = [Reason.typo_domain, Reason.possible_typo_trap]
        return _with_flags(Verdict.risky, _DO_NOT_SEND, Confidence.medium, reasons, flags)

    if probe is not None and probe.outcome is not ProbeOutcome.not_run:
        return _probed(probe, flags, probe_reason, provider_reliability)

    skipped: list[Reason] = [Reason.probe_skipped] if probe is not None else []
    has_mx = domain is not None and bool(domain.mx)
    negative = flags.role or flags.gibberish
    confidence = Confidence.medium if has_mx and not negative else Confidence.low
    return _with_flags(Verdict.unknown, _RISKY, confidence, skipped, flags)
