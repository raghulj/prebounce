"""Address parsing and syntax checks. No network access.

Syntax follows RFC 5321/5322 with the RFC 6531 (SMTPUTF8) extension for the local part:

* local part: a dot-atom or a quoted string, at most 64 octets (UTF-8, quotes included);
* whole address: at most 254 octets, with the domain measured in its ASCII (punycode) form;
* domain: at least two LDH labels of at most 63 characters, no empty labels, no leading or
  trailing hyphen, an all-numeric top-level label is rejected.

Deliberate choices:

* Domain literals such as ``user@[192.0.2.1]`` and bare IP domains are rejected with
  ``syntax_domain_invalid``: they are valid RFC 5321 but never a mailbox worth verifying.
* An empty quoted local part (``""@example.com``) is rejected.
* Display names and angle brackets are not accepted; pass a plain address.
* The domain is converted with Python's ``idna`` codec (IDNA 2003 mapping).

When the optional ``email-validator`` package is importable it is consulted as a second opinion:
it can only turn a valid verdict into ``syntax_invalid``, never the reverse.
"""

from __future__ import annotations

import importlib
import re
import unicodedata
from typing import Any

from prebounce.types import Reason

_MAX_LOCAL = 64
_MAX_ADDRESS = 254
_MAX_DOMAIN = 253
_ATEXT = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~"
)
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", re.ASCII | re.IGNORECASE)


def _to_ascii_domain(domain: str) -> str | None:
    """Return the lower-case ASCII (punycode) form of domain, or None if it cannot be encoded."""
    try:
        return domain.lower().encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return None


def normalize(address: str) -> tuple[str, str, str]:
    """Return (normalized, local, domain).

    Trims whitespace, lower-cases the domain (IDNA/punycode to ASCII), NFC-normalises the local
    part and preserves its case. Never raises: input without an @ returns (stripped, stripped, "").
    """
    stripped = address.strip()
    local, at, domain = stripped.rpartition("@")
    if not at:
        return stripped, stripped, ""
    local = unicodedata.normalize("NFC", local)
    ascii_domain = _to_ascii_domain(domain)
    domain = ascii_domain if ascii_domain is not None else domain.lower()
    return f"{local}@{domain}", local, domain


def _allowed_non_ascii(ch: str) -> bool:
    return ord(ch) > 127 and unicodedata.category(ch)[0] not in "CZ"


def _split(s: str) -> tuple[str, str, Reason | None]:
    """Split at the @ that ends the local part; the Reason is set when no split is possible."""
    if s.startswith('"'):
        i = 1
        while i < len(s):
            if s[i] == "\\":
                i += 2
                continue
            if s[i] == '"':
                break
            i += 1
        else:
            return "", "", Reason.syntax_invalid if "@" in s else Reason.syntax_no_at_sign
        if s[i + 1 : i + 2] != "@":
            return "", "", Reason.syntax_invalid if "@" in s[i + 1 :] else Reason.syntax_no_at_sign
        local, domain = s[: i + 1], s[i + 2 :]
    else:
        idx = s.find("@")
        if idx < 0:
            return "", "", Reason.syntax_no_at_sign
        local, domain = s[:idx], s[idx + 1 :]
    if "@" in domain:
        return "", "", Reason.syntax_too_many_at_signs
    return local, domain, None


def _local_valid(local: str) -> bool:
    if local.startswith('"'):
        content = local[1:-1]
        if not content:
            return False
        i = 0
        while i < len(content):
            ch = content[i]
            if ch == "\\":
                if i + 1 >= len(content):
                    return False
                nxt = content[i + 1]
                if not (32 <= ord(nxt) <= 126 or _allowed_non_ascii(nxt)):
                    return False
                i += 2
                continue
            if ch == '"' or not (32 <= ord(ch) <= 126 or _allowed_non_ascii(ch)):
                return False
            i += 1
        return True
    if not local or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    return all(ch == "." or ch in _ATEXT or _allowed_non_ascii(ch) for ch in local)


def _maps_to_punctuation(ch: str) -> bool:
    """True for a non-ASCII character that IDNA mapping would turn into ASCII punctuation."""
    if ch.isascii() or ch in "\u3002\uff0e\uff61":
        return False
    mapped = unicodedata.normalize("NFKC", ch.lower())
    return any(c.isascii() and not (c.isalnum() or c == "-") for c in mapped)


def _domain_ascii_if_valid(domain: str) -> str | None:
    """Return the ASCII form of domain if it is a valid mail domain, else None."""
    if not domain or domain.startswith("["):
        return None
    if any(_maps_to_punctuation(ch) for ch in domain):
        return None
    ascii_domain = _to_ascii_domain(domain)
    if ascii_domain is None or len(ascii_domain) > _MAX_DOMAIN:
        return None
    labels = ascii_domain.split(".")
    if len(labels) < 2 or labels[-1].isdigit():
        return None
    for label in labels:
        if len(label) > 63 or not _LABEL.fullmatch(label):
            return None
        if label[2:4] == "--":
            if not label.startswith("xn--"):
                return None
            try:
                label.encode("ascii").decode("idna")
            except (UnicodeError, ValueError):
                return None
    return ascii_domain


def _email_validator_rejects(address: str) -> bool:
    module = _load_email_validator()
    if module is None:
        return False
    try:
        module.validate_email(
            address,
            check_deliverability=False,
            allow_quoted_local=True,
            allow_smtputf8=True,
            test_environment=True,
        )
    except module.EmailNotValidError:
        return True
    return False


def _load_email_validator() -> Any | None:
    try:
        return importlib.import_module("email_validator")
    except ImportError:
        return None


def check_syntax(address: str) -> tuple[Reason, ...]:
    """Return the syntax_* reasons that apply; an empty tuple means the address is valid.

    Surrounding whitespace is ignored, as in normalize.
    """
    s = address.strip()
    local, domain, split_error = _split(s)
    if split_error is not None:
        return (split_error,)
    reasons: list[Reason] = []
    if not _local_valid(local):
        reasons.append(Reason.syntax_invalid)
    if len(local.encode("utf-8")) > _MAX_LOCAL:
        reasons.append(Reason.syntax_local_too_long)
    ascii_domain = _domain_ascii_if_valid(domain)
    if ascii_domain is None:
        reasons.append(Reason.syntax_domain_invalid)
    if (
        len(local.encode("utf-8")) + 1 + len((ascii_domain or domain).encode("utf-8"))
        > _MAX_ADDRESS
    ):
        reasons.append(Reason.syntax_address_too_long)
    if not reasons and _email_validator_rejects(s):
        reasons.append(Reason.syntax_invalid)
    return tuple(reasons)
