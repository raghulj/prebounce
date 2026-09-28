"""Tests for prebounce.address.

Vectors are adapted (not copied as code) from:
* python-email-validator tests/test_syntax.py (Unlicense),
  https://github.com/JoshData/python-email-validator
* RFC 3696 section 3 examples.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from prebounce import address
from prebounce.address import check_syntax, normalize
from prebounce.types import Reason

OK = ()
INVALID = (Reason.syntax_invalid,)
DOMAIN = (Reason.syntax_domain_invalid,)


@pytest.fixture(autouse=True)
def _no_email_validator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(address, "_load_email_validator", lambda: None)


# python-email-validator test_email_valid / test_email_valid_only_if_quoted_local_part,
# RFC 3696 section 3 ("Abc\@def"@example.com style examples).
VALID = [
    "Abc@example.tld",
    "Abc.123@test-example.com",
    "user+mailbox/department=shipping@example.tld",
    "!#$%&'*+-/=?^_`.{|}~@example.tld",
    "jeff@臺網中心.tw",
    '"quoted local part"@example.org',
    '"de-quoted.local.part"@example.org',
    '"unnecessary.escaped.\\x.local.part"@example.org',
    '"escaped.quote.\\".local.part"@example.org',
    '"quoted..local.part"@example.com',
    '"quoted.with.at@"@example.com',
    '"quoted.with.dquote\\""@example.com',
    '"unnecessarily.quoted.with.unicode.λ"@example.com',
    "伊昭傑@郵件.商務",
    "राम@मोहन.ईन्फो",
    "üser@example.com",
    "a@b.co",
    "x@xn--fiqq24b10vi0d.tw",
    "  padded@example.com  ",
    "first.last@sub.domain.example.org",
    "a" * 64 + "@example.com",
    "user@" + "a" * 63 + ".com",
    '"much.more unusual"@example.com',
    '"very.unusual.@.unusual.com"@example.com',
    "customer/department=shipping@example.com",
    "$A12345@example.com",
    "!def!xyz%abc@example.com",
    "_somename@example.com",
    "user@localdomain.co.uk",
    "Pete@silly.test",
    "1234567890@example.com",
    "mixedCASE@Example.COM",
]

# python-email-validator test_email_invalid_syntax, mapped to reason codes.
INVALID_CASES: list[tuple[str, tuple[Reason, ...]]] = [
    ("hello.world", (Reason.syntax_no_at_sign,)),
    ("hello＠world", (Reason.syntax_no_at_sign,)),
    ("", (Reason.syntax_no_at_sign,)),
    ("my@localhost", DOMAIN),
    ("my@.leadingdot.com", DOMAIN),
    ("my@．leadingfwdot.com", DOMAIN),
    ("my@twodots..com", DOMAIN),
    ("my@trailingdot.com.", DOMAIN),
    ("me@-leadingdash", DOMAIN),
    ("me@trailingdash-", DOMAIN),
    ("my@baddash.-.com", DOMAIN),
    ("my@baddash.-a.com", DOMAIN),
    ("my@baddash.b-.com", DOMAIN),
    ("my@example\n.com", DOMAIN),
    ("me@x!", DOMAIN),
    ("test@white space", DOMAIN),
    ("me@⒈wouldbeinvalid.com", DOMAIN),
    ("me@xn--0.tld", DOMAIN),
    ("me@yy--0.tld", DOMAIN),
    ("me@bad.192", DOMAIN),
    ("me@192.168.0.1", DOMAIN),
    ("me@[127.0.0.1]", DOMAIN),
    ("me@[IPv6:::1]", DOMAIN),
    ("me@[tag:text]", DOMAIN),
    ("me@", DOMAIN),
    (".leadingdot@domain.com", INVALID),
    ("twodots..here@domain.com", INVALID),
    ("trailingdot.@domain.email", INVALID),
    ("@example.com", INVALID),
    ("white space@test.com", INVALID),
    ("m\ny@example.com", INVALID),
    ("bad" + '"quotes"' + "@example.com", INVALID),
    ('obsolete."quoted".atom@example.com', INVALID),
    ('""@example.com', INVALID),
    ('"unterminated@example.com', INVALID),
    ('"quoted"junk@example.com', INVALID),
    ("<me@example.com>", INVALID + DOMAIN),
    ("Display Name <me@example.com>", INVALID + DOMAIN),
    ("a@b@example.com", (Reason.syntax_too_many_at_signs,)),
    ("@@", (Reason.syntax_too_many_at_signs,)),
    ("a" * 65 + "@example.com", (Reason.syntax_local_too_long,)),
    ("é" * 33 + "@example.com", (Reason.syntax_local_too_long,)),
    ("me@" + "a" * 64 + ".com", DOMAIN),
]


@pytest.mark.parametrize("value", VALID)
def test_valid_addresses(value: str) -> None:
    assert check_syntax(value) == OK


@pytest.mark.parametrize(("value", "expected"), INVALID_CASES)
def test_invalid_addresses(value: str, expected: tuple[Reason, ...]) -> None:
    assert check_syntax(value) == expected


def test_case_count() -> None:
    assert len(VALID) + len(INVALID_CASES) >= 40


def test_whole_address_length_limit() -> None:
    label = "a" * 63
    at_limit = "u@" + ".".join([label, label, label, "a" * 59])  # 2 + 63*3 + 3 + 59 = 253 domain+2
    assert len(at_limit) <= 254
    assert check_syntax(at_limit) == OK
    too_long = "u" * 10 + "@" + ".".join([label, label, label, "a" * 60])
    assert len(too_long) > 254
    assert Reason.syntax_address_too_long in check_syntax(too_long)


def test_address_too_long_reported_with_domain_error() -> None:
    value = "u" * 64 + "@" + "a" * 200 + "." + "b" * 200
    reasons = check_syntax(value)
    assert Reason.syntax_address_too_long in reasons
    assert Reason.syntax_domain_invalid in reasons


def test_local_part_limit_is_octets_not_characters() -> None:
    assert check_syntax("é" * 32 + "@example.com") == OK
    assert check_syntax("é" * 33 + "@example.com") == (Reason.syntax_local_too_long,)


def test_multiple_problems_are_all_reported() -> None:
    assert check_syntax("a..b@-x.com") == INVALID + DOMAIN


def test_surrounding_whitespace_ignored_but_internal_rejected() -> None:
    assert check_syntax("\tme@example.com\n") == OK
    assert check_syntax("me @example.com") == INVALID


# ---------------------------------------------------------------- normalisation


def test_normalize_lowercases_domain_and_keeps_local_case() -> None:
    assert normalize("  John.Smith@Example.COM ") == (
        "John.Smith@example.com",
        "John.Smith",
        "example.com",
    )


def test_normalize_idna_encodes_domain() -> None:
    assert normalize("jeff@臺網中心.TW") == (
        "jeff@xn--fiqq24b10vi0d.tw",
        "jeff",
        "xn--fiqq24b10vi0d.tw",
    )


def test_normalize_is_idempotent() -> None:
    once = normalize("Üser@BÜCHER.example")[0]
    assert normalize(once)[0] == once


def test_normalize_nfc_local_part() -> None:
    decomposed = "café@example.com"
    normalized, local, _ = normalize(decomposed)
    assert local == "café"
    assert normalized == "café@example.com"


def test_normalize_without_at_sign() -> None:
    assert normalize("  nothing  ") == ("nothing", "nothing", "")


def test_normalize_empty() -> None:
    assert normalize("   ") == ("", "", "")


def test_normalize_uses_last_at_sign_so_quoted_at_survives() -> None:
    normalized, local, domain = normalize('"a@b"@Example.com')
    assert (local, domain) == ('"a@b"', "example.com")
    assert normalized == '"a@b"@example.com'


def test_normalize_keeps_unencodable_domain_lowercased() -> None:
    assert normalize("a@Bad..Domain")[2] == "bad..domain"


def test_normalize_output_passes_syntax_when_input_does() -> None:
    for value in VALID:
        assert check_syntax(normalize(value)[0]) == OK


# ---------------------------------------------------------------- email-validator cross-check


def _fake_module(reject: bool) -> types.ModuleType:
    module = types.ModuleType("email_validator")

    class EmailNotValidError(ValueError):
        pass

    def validate_email(value: str, **kwargs: Any) -> None:
        assert kwargs["check_deliverability"] is False
        if reject:
            raise EmailNotValidError(value)

    module.EmailNotValidError = EmailNotValidError  # type: ignore[attr-defined]
    module.validate_email = validate_email  # type: ignore[attr-defined]
    return module


def test_email_validator_can_veto_a_valid_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(address, "_load_email_validator", lambda: _fake_module(reject=True))
    assert check_syntax("me@example.com") == INVALID


def test_email_validator_agreeing_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(address, "_load_email_validator", lambda: _fake_module(reject=False))
    assert check_syntax("me@example.com") == OK


def test_email_validator_not_consulted_when_builtin_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(address, "_load_email_validator", lambda: _fake_module(reject=False))
    assert check_syntax("nope") == (Reason.syntax_no_at_sign,)


def test_load_email_validator_returns_module_or_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    monkeypatch.setitem(sys.modules, "email_validator", None)
    assert address._load_email_validator() is None
    fake = _fake_module(reject=False)
    monkeypatch.setitem(sys.modules, "email_validator", fake)
    assert address._load_email_validator() is fake
