"""Address parsing and syntax checks. No network access."""

from __future__ import annotations

from prebounce.types import Reason


def normalize(address: str) -> tuple[str, str, str]:
    """Return (normalized, local, domain).

    Trims whitespace, lower-cases the domain (IDNA/punycode to ASCII), preserves the local part.
    Never raises: input that cannot be split returns (stripped, stripped, "") .
    """
    raise NotImplementedError


def check_syntax(address: str) -> tuple[Reason, ...]:
    """Return the syntax_* reasons that apply; an empty tuple means the address is valid."""
    raise NotImplementedError
