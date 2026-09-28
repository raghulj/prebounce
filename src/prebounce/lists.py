"""Offline lists and heuristics: disposable domains, role names, free providers, typos."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from prebounce.protocols import Cache


@dataclass(frozen=True)
class RefreshReport:
    """Outcome of refresh_domain_lists."""

    source_count: int
    domains_added: int
    domains_total: int
    errors: tuple[str, ...] = ()


def is_role(local: str) -> bool:
    """True if the local part is a role mailbox such as info, admin or support."""
    raise NotImplementedError


def is_free_provider(domain: str) -> bool:
    """True if domain is a public free mailbox provider such as gmail.com."""
    raise NotImplementedError


def suggest_domain(domain: str) -> str | None:
    """Return the likely intended domain for a misspelling (gmial.com -> gmail.com), else None."""
    raise NotImplementedError


def gibberish_score(local: str) -> float:
    """Return 0.0 (natural) to 1.0 (random keyboard mash) for a local part."""
    raise NotImplementedError


class DisposableLists:
    """Disposable and allow lists; implements the DomainLists protocol."""

    def __init__(self, disposable: Iterable[str] = (), allow: Iterable[str] = ()) -> None:
        """Start from the given sets (not the bundle); use load_bundled for the snapshot."""
        raise NotImplementedError

    @classmethod
    def load_bundled(cls) -> DisposableLists:
        """Load the snapshot shipped in prebounce/data."""
        raise NotImplementedError

    def disposable(self) -> frozenset[str]:
        raise NotImplementedError

    def allow(self) -> frozenset[str]:
        raise NotImplementedError

    def is_disposable(self, domain: str) -> bool:
        """True if domain or any parent domain is listed and no allow entry covers it."""
        raise NotImplementedError

    def merge(self, disposable: Iterable[str] = (), allow: Iterable[str] = ()) -> DisposableLists:
        """Return a new instance with the extra entries added."""
        raise NotImplementedError


def refresh_domain_lists(fetch: Callable[[str], str], store: Cache) -> RefreshReport:
    """Fetch upstream list sources via fetch(url) -> text and save the merged result in store.

    The library itself never opens sockets here; the host supplies fetch.
    """
    raise NotImplementedError
