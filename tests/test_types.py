from datetime import datetime, timezone

import pytest

from prebounce import (
    Confidence,
    DomainInfo,
    Flags,
    MxRecord,
    PendingState,
    PrebounceError,
    ProbeOutcome,
    ProbeResult,
    Reason,
    Result,
    SendRecommendation,
    SmtpReply,
    Status,
    Verdict,
)


def _full_result() -> Result:
    return Result(
        address=" Lee@Example.com ",
        normalized="Lee@example.com",
        status=Status.complete,
        verdict=Verdict.risky,
        send=SendRecommendation.risky_to_send,
        confidence=Confidence.medium,
        reasons=(Reason.accept_all, Reason.free_provider),
        flags=Flags(free=True, catch_all=True),
        suggestion="lee@example.org",
        domain=DomainInfo("example.com", True, (MxRecord(10, "mx.example.com"),), provider="x"),
        probe=ProbeResult(
            ProbeOutcome.accepted,
            SmtpReply(250, "2.1.5", "OK"),
            ProbeOutcome.accepted,
            "mx.example.com",
            "socks5://p:1080",
            ("C: RCPT", "S: 250 OK"),
        ),
        provider="x",
        source="probe",
        checked_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )


def test_result_round_trip_through_json() -> None:
    import json

    result = _full_result()
    data = json.loads(json.dumps(result.to_dict()))
    assert Result.from_dict(data) == result


def test_result_round_trip_with_pending_and_minimal_fields() -> None:
    pending = PendingState("a@b.com", 1, 3, 330)
    result = Result(
        "a@b.com",
        "a@b.com",
        Status.pending,
        Verdict.unknown,
        SendRecommendation.risky_to_send,
        Confidence.low,
        (Reason.greylisted,),
        pending=pending,
    )
    restored = Result.from_dict(result.to_dict())
    assert restored == result
    assert restored.checked_at.tzinfo is not None


def test_pending_token_round_trip() -> None:
    state = PendingState("a@b.com", 2, 3, 330, proxy="socks5://p:1", mx_host="mx.b.com")
    token = state.to_token()
    assert token.startswith("v1.")
    assert PendingState.from_token(token) == state


@pytest.mark.parametrize("token", ["", "v2.abc", "v1.!!!", "v1.e30", "nodot"])
def test_pending_token_rejects_bad_input(token: str) -> None:
    with pytest.raises(PrebounceError):
        PendingState.from_token(token)


@pytest.mark.parametrize(
    ("code", "positive", "transient", "permanent"),
    [
        (250, True, False, False),
        (354, True, False, False),
        (451, False, True, False),
        (550, False, False, True),
        (421, False, True, False),
    ],
)
def test_smtp_reply_properties(code: int, positive: bool, transient: bool, permanent: bool) -> None:
    reply = SmtpReply(code, None, "x")
    assert (reply.is_positive, reply.is_transient, reply.is_permanent) == (
        positive,
        transient,
        permanent,
    )
