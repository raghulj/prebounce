"""Table-driven checks of every scoring rule and the precedence between them."""

from __future__ import annotations

from typing import Any

import pytest

from prebounce.scoring import score
from prebounce.types import (
    Confidence as C,
)
from prebounce.types import (
    DomainInfo,
    Flags,
    MxRecord,
    ProbeOutcome,
    ProbeResult,
    SmtpReply,
)
from prebounce.types import Reason as R
from prebounce.types import SendRecommendation as S
from prebounce.types import Verdict as V

MX = (MxRecord(10, "mx.example.com"),)
GOOD = DomainInfo("example.com", True, mx=MX)
REPLY = SmtpReply(250, None, "ok")


def run(
    *,
    syntax: tuple[R, ...] = (),
    flags: Flags | None = None,
    domain: DomainInfo | None = None,
    probe: ProbeResult | None = None,
    probe_reason: R | None = None,
    reliability: str | None = None,
    suggestion: str | None = None,
) -> tuple[V, S, C, tuple[R, ...]]:
    return score(
        syntax, flags or Flags(), domain, probe, probe_reason, reliability, suggestion, False
    )


def probe(
    outcome: ProbeOutcome, catch_all: ProbeOutcome = ProbeOutcome.not_run, reply: bool = True
) -> ProbeResult:
    return ProbeResult(outcome, REPLY if reply else None, catch_all)


A, RF, INC, NR = (
    ProbeOutcome.accepted,
    ProbeOutcome.refused,
    ProbeOutcome.inconclusive,
    ProbeOutcome.not_run,
)

CASES: list[tuple[str, dict[str, Any], tuple[V, S, C, tuple[R, ...]]]] = [
    (
        "syntax",
        {"syntax": (R.syntax_invalid, R.syntax_domain_invalid)},
        (V.undeliverable, S.do_not_send, C.high, (R.syntax_invalid, R.syntax_domain_invalid)),
    ),
    (
        "disposable",
        {"flags": Flags(disposable=True)},
        (V.undeliverable, S.do_not_send, C.high, (R.disposable_domain,)),
    ),
    (
        "domain missing",
        {"domain": DomainInfo("x.com", False)},
        (V.undeliverable, S.do_not_send, C.high, (R.domain_not_found,)),
    ),
    (
        "no mx",
        {"domain": DomainInfo("x.com", True)},
        (V.undeliverable, S.do_not_send, C.high, (R.no_mx,)),
    ),
    (
        "null mx",
        {"domain": DomainInfo("x.com", True, null_mx=True)},
        (V.undeliverable, S.do_not_send, C.high, (R.null_mx,)),
    ),
    (
        "blocklisted",
        {"domain": DomainInfo("x.com", True, mx=MX, blocklisted=("dbl",))},
        (V.risky, S.do_not_send, C.medium, (R.domain_blocklisted,)),
    ),
    (
        "typo",
        {"suggestion": "jane@gmail.com"},
        (V.risky, S.do_not_send, C.medium, (R.typo_domain, R.possible_typo_trap)),
    ),
    (
        "typo with dns ok",
        {"suggestion": "jane@gmail.com", "domain": GOOD},
        (V.risky, S.do_not_send, C.medium, (R.typo_domain, R.possible_typo_trap)),
    ),
    (
        "no probe, no domain",
        {},
        (V.unknown, S.risky_to_send, C.low, ()),
    ),
    (
        "no probe, mx",
        {"domain": GOOD},
        (V.unknown, S.risky_to_send, C.medium, ()),
    ),
    (
        "no probe, implicit mx",
        {"domain": DomainInfo("x.com", True, mx=(MxRecord(0, "x.com"),), implicit_mx=True)},
        (V.unknown, S.risky_to_send, C.medium, ()),
    ),
    (
        "no probe, mx, role",
        {"domain": GOOD, "flags": Flags(role=True)},
        (V.unknown, S.risky_to_send, C.low, (R.role_address,)),
    ),
    (
        "no probe, mx, gibberish",
        {"domain": GOOD, "flags": Flags(gibberish=True)},
        (V.unknown, S.risky_to_send, C.low, (R.gibberish,)),
    ),
    (
        "no probe, free provider only",
        {"domain": GOOD, "flags": Flags(free=True)},
        (V.unknown, S.risky_to_send, C.medium, ()),
    ),
    (
        "probe not run",
        {"domain": GOOD, "probe": probe(NR)},
        (V.unknown, S.risky_to_send, C.medium, (R.probe_skipped,)),
    ),
    (
        "accepted, catch-all refused",
        {"domain": GOOD, "probe": probe(A, RF)},
        (V.deliverable, S.safe_to_send, C.high, (R.mailbox_accepted,)),
    ),
    (
        "accepted, catch-all accepted",
        {"domain": GOOD, "probe": probe(A, A)},
        (V.risky, S.risky_to_send, C.low, (R.mailbox_accepted, R.accept_all)),
    ),
    (
        "accepted, catch-all untested",
        {"domain": GOOD, "probe": probe(A)},
        (V.deliverable, S.risky_to_send, C.medium, (R.mailbox_accepted,)),
    ),
    (
        "accepted, gateway provider",
        {"domain": GOOD, "probe": probe(A, RF), "reliability": "accept_all_gateway"},
        (
            V.risky,
            S.risky_to_send,
            C.low,
            (R.mailbox_accepted, R.security_gateway, R.accept_all),
        ),
    ),
    (
        "accepted, unreliable provider",
        {"domain": GOOD, "probe": probe(A, RF), "reliability": "unreliable"},
        (V.unknown, S.risky_to_send, C.low, (R.provider_unreliable,)),
    ),
    (
        "accepted, reliable provider",
        {"domain": GOOD, "probe": probe(A, RF), "reliability": "reliable"},
        (V.deliverable, S.safe_to_send, C.high, (R.mailbox_accepted,)),
    ),
    (
        "accepted, role lowers send",
        {"domain": GOOD, "probe": probe(A, RF), "flags": Flags(role=True)},
        (V.deliverable, S.risky_to_send, C.high, (R.mailbox_accepted, R.role_address)),
    ),
    (
        "accepted, role and gibberish",
        {"domain": GOOD, "probe": probe(A, RF), "flags": Flags(role=True, gibberish=True)},
        (
            V.deliverable,
            S.risky_to_send,
            C.high,
            (R.mailbox_accepted, R.role_address, R.gibberish),
        ),
    ),
    (
        "refused, not found",
        {"domain": GOOD, "probe": probe(RF), "probe_reason": R.mailbox_not_found},
        (V.undeliverable, S.do_not_send, C.high, (R.mailbox_not_found,)),
    ),
    (
        "refused, disabled",
        {"domain": GOOD, "probe": probe(RF), "probe_reason": R.mailbox_disabled},
        (V.undeliverable, S.do_not_send, C.high, (R.mailbox_disabled,)),
    ),
    (
        "refused, no reason defaults to not found",
        {"domain": GOOD, "probe": probe(RF)},
        (V.undeliverable, S.do_not_send, C.high, (R.mailbox_not_found,)),
    ),
    (
        "refused, full",
        {"domain": GOOD, "probe": probe(RF), "probe_reason": R.mailbox_full},
        (V.risky, S.risky_to_send, C.medium, (R.mailbox_full,)),
    ),
    (
        "inconclusive keeps reason",
        {"domain": GOOD, "probe": probe(INC), "probe_reason": R.greylisted},
        (V.unknown, S.risky_to_send, C.low, (R.greylisted,)),
    ),
    (
        "inconclusive blocked",
        {"domain": GOOD, "probe": probe(INC), "probe_reason": R.prober_blocked},
        (V.unknown, S.risky_to_send, C.low, (R.prober_blocked,)),
    ),
    (
        "inconclusive, no reply",
        {"domain": GOOD, "probe": probe(INC, reply=False)},
        (V.unknown, S.risky_to_send, C.low, (R.connection_failed,)),
    ),
    (
        "inconclusive, reply without reason",
        {"domain": GOOD, "probe": probe(INC)},
        (V.unknown, S.risky_to_send, C.low, (R.temporary_failure,)),
    ),
    (
        "inconclusive, unreliable provider",
        {
            "domain": GOOD,
            "probe": probe(INC),
            "probe_reason": R.temporary_failure,
            "reliability": "unreliable",
        },
        (V.unknown, S.risky_to_send, C.low, (R.temporary_failure, R.provider_unreliable)),
    ),
    # precedence
    (
        "syntax beats disposable",
        {"syntax": (R.syntax_invalid,), "flags": Flags(disposable=True)},
        (V.undeliverable, S.do_not_send, C.high, (R.syntax_invalid,)),
    ),
    (
        "disposable beats dns",
        {"flags": Flags(disposable=True), "domain": DomainInfo("x.com", False)},
        (V.undeliverable, S.do_not_send, C.high, (R.disposable_domain,)),
    ),
    (
        "dns beats blocklist",
        {"domain": DomainInfo("x.com", True, blocklisted=("dbl",))},
        (V.undeliverable, S.do_not_send, C.high, (R.no_mx,)),
    ),
    (
        "dns beats typo",
        {"domain": DomainInfo("x.com", False), "suggestion": "a@b.com"},
        (V.undeliverable, S.do_not_send, C.high, (R.domain_not_found,)),
    ),
    (
        "blocklist beats typo",
        {
            "domain": DomainInfo("x.com", True, mx=MX, blocklisted=("dbl",)),
            "suggestion": "a@b.com",
        },
        (V.risky, S.do_not_send, C.medium, (R.domain_blocklisted,)),
    ),
    (
        "typo beats probe",
        {"domain": GOOD, "suggestion": "a@b.com", "probe": probe(A, RF)},
        (V.risky, S.do_not_send, C.medium, (R.typo_domain, R.possible_typo_trap)),
    ),
    (
        "domain beats probe",
        {"domain": DomainInfo("x.com", False), "probe": probe(A, RF)},
        (V.undeliverable, S.do_not_send, C.high, (R.domain_not_found,)),
    ),
    (
        "typo with role keeps do_not_send, adds reason",
        {"suggestion": "a@b.com", "flags": Flags(role=True)},
        (
            V.risky,
            S.do_not_send,
            C.medium,
            (R.typo_domain, R.possible_typo_trap, R.role_address),
        ),
    ),
    (
        "refused with role stays undeliverable",
        {"domain": GOOD, "probe": probe(RF), "flags": Flags(role=True)},
        (V.undeliverable, S.do_not_send, C.high, (R.mailbox_not_found, R.role_address)),
    ),
]


@pytest.mark.parametrize(("kwargs", "expected"), [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_score(kwargs: dict[str, Any], expected: tuple[V, S, C, tuple[R, ...]]) -> None:
    assert run(**kwargs) == expected


def test_strict_only_match_lowers_confidence() -> None:
    flags = Flags(disposable=True)
    core = score((), flags, None, None, None, None, None, False)
    strict = score((), flags, None, None, None, None, None, True)
    assert core == (V.undeliverable, S.do_not_send, C.high, (R.disposable_domain,))
    assert strict == (V.undeliverable, S.do_not_send, C.medium, (R.disposable_domain,))


def test_reasons_are_deduplicated_and_deterministic() -> None:
    args = {"domain": GOOD, "probe": probe(A, RF), "flags": Flags(role=True, gibberish=True)}
    assert run(**args) == run(**args)
    assert len(set(run(**args)[3])) == len(run(**args)[3])
