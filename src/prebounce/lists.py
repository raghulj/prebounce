"""Offline lists and heuristics: disposable domains, role names, free providers, typos.

Disposable matching rule: a domain is checked, then each parent domain, removing the leftmost
label each time, until two labels remain (``a.b.tempmail.example`` is caught by
``tempmail.example``). No public suffix list is used, so a listed entry with two labels is the
shortest match ever attempted; ``co.uk`` style suffixes are never matched by a third-party
name. An allow entry on the domain or any of the parents wins over a disposable entry, and a
free provider domain is never disposable.

The strict list (disposable/disposable-email-domains) is much larger and has more false positives.
It is kept apart from the core lists, loaded only on request and consulted only when the host
turns on ``strict_disposable``.

Refresh storage (see refresh_domain_lists): every key is prefixed ``prebounce:lists:v1:``.
``source:<name>`` holds ``{"domains": [...], "count": n, "fetched_at": iso}`` for each accepted
upstream source, ``disposable``, ``allow`` and (when refreshed with strict=True) ``strict`` hold
``{"domains": [...]}`` for the merged result. All are stored with a 90 day TTL.
"""

from __future__ import annotations

import contextlib
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from importlib import resources

from prebounce.protocols import Cache, DomainLists, StrictDomainLists

_KEY_PREFIX = "prebounce:lists:v1:"
_KEY_DISPOSABLE = _KEY_PREFIX + "disposable"
_KEY_ALLOW = _KEY_PREFIX + "allow"
_KEY_STRICT = _KEY_PREFIX + "strict"
_STORE_TTL = 90 * 86400
_MAX_SHRINK_RATIO = 0.5
_MAX_INVALID_RATIO = 0.01

_SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "primary",
        "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/"
        "main/disposable_email_blocklist.conf",
        "disposable",
    ),
    (
        "fakefilter",
        "https://raw.githubusercontent.com/7c/fakefilter/main/txt/data.txt",
        "disposable",
    ),
    (
        "allow",
        "https://raw.githubusercontent.com/amieiro/disposable-email-domains/master/"
        "allowDomains.txt",
        "allow",
    ),
    (
        "strict",
        "https://raw.githubusercontent.com/disposable/disposable-email-domains/master/domains.txt",
        "strict",
    ),
)

_HOSTNAME = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
    re.ASCII,
)


@dataclass(frozen=True)
class RefreshReport:
    """Outcome of refresh_domain_lists."""

    source_count: int
    domains_added: int
    domains_total: int
    errors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------------------------
# bundled data


def _read_data(name: str) -> str:
    return (resources.files("prebounce") / "data" / name).read_text(encoding="utf-8")


def _parse_domains(text: str) -> list[str]:
    """Parse a one-domain-per-line file, dropping comments and blank lines."""
    out: list[str] = []
    for line in text.splitlines():
        fields = line.split("#", 1)[0].split()
        if fields:
            out.append(fields[0])
    return out


def _clean(entry: str) -> str:
    """Lower-case, strip a trailing dot and convert to IDNA form where possible."""
    value = entry.strip().lower().rstrip(".")
    if value and not value.isascii():
        with contextlib.suppress(UnicodeError):
            value = value.encode("idna").decode("ascii")
    return value


def _clean_all(entries: Iterable[str]) -> frozenset[str]:
    return frozenset(c for c in (_clean(e) for e in entries) if c)


@lru_cache(maxsize=1)
def _free_providers() -> frozenset[str]:
    return _clean_all(_parse_domains(_read_data("free_providers.txt")))


# ---------------------------------------------------------------------------------------------
# role and free provider detection


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_ROLE_LOCALS = _words(
    """
    abuse accounting accounts admin administrator advertising all billing booking bookings
    careers compliance contact contactus customerservice customer-service dns editor
    enquiries enquiry events feedback finance ftp hello help helpdesk hostmaster hr info
    it jobs legal list mail mailer-daemon mailerdaemon manager marketing media news
    newsletter no-reply no_reply noreply nobody noc office operations orders payments
    postmaster press privacy procurement psirt recruiting recruitment registrar reception
    reply root sales security service services shop staff subscribe support sysadmin team
    tech unsubscribe usenet uucp webmaster www
    """
)


def is_role(local: str) -> bool:
    """True if the local part is a role mailbox such as info, admin or support.

    A ``+tag`` suffix is ignored (``sales+eu`` is a role); dots and hyphens are not stripped.
    """
    base = local.strip().lower().split("+", 1)[0]
    return base in _ROLE_LOCALS


def is_free_provider(domain: str) -> bool:
    """True if domain is a public free mailbox provider such as gmail.com."""
    return _clean(domain) in _free_providers()


# ---------------------------------------------------------------------------------------------
# typo suggestions

# Ordered by popularity: ties in edit distance go to the earlier entry.
_POPULAR_DOMAINS: tuple[str, ...] = (
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "live.com",
    "msn.com",
    "comcast.net",
    "me.com",
    "mac.com",
    "protonmail.com",
    "proton.me",
    "googlemail.com",
    "ymail.com",
    "gmx.com",
    "gmx.net",
    "gmx.de",
    "web.de",
    "mail.com",
    "mail.ru",
    "yandex.ru",
    "yandex.com",
    "qq.com",
    "163.com",
    "126.com",
    "naver.com",
    "att.net",
    "verizon.net",
    "sbcglobal.net",
    "bellsouth.net",
    "cox.net",
    "btinternet.com",
    "orange.fr",
    "free.fr",
    "t-online.de",
    "libero.it",
    "hotmail.co.uk",
    "yahoo.co.uk",
    "live.co.uk",
    "zoho.com",
    "fastmail.com",
    "tutanota.com",
)


@lru_cache(maxsize=1)
def _known_domains() -> frozenset[str]:
    return _free_providers() | frozenset(_POPULAR_DOMAINS)


_GENERIC_TLDS = _words(
    """
com net org edu gov mil int info biz name pro mobi asia tel xxx app dev xyz online site shop store
tech top club cam cat coop museum aero travel jobs post art bar bid bio blog buzz cab car care
city click cloud codes college community company cool cyou date design digital direct domains
email exchange expert fun global group guru host icu ink kim land life link live love ltd management
market media moe network news nyc one ovh page party pics plus press rest review rocks run
services show social solutions space studio support systems team today tools town trade
university uno vip website wiki win work works world zone
"""
)

_COUNTRY_TLDS = _words(
    """
ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bm bn bo br bs bt bw
by bz ca cc cd cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm do dz ec ee eg er es
et eu fi fj fk fm fo fr ga gd ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu
id ie il im in io iq ir is it je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls
lt lu lv ly ma mc md me mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na nc ne nf ng ni
nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa re ro rs ru rw sa sb sc sd se
sg sh si sk sl sm sn so sr ss st su sv sx sy sz tc td tf tg th tj tk tl tm tn to tr tt tv tw tz
ua ug uk us uy uz va vc ve vg vi vn vu wf ws ye yt za zm zw
"""
)

_VALID_TLDS = _GENERIC_TLDS | _COUNTRY_TLDS
_TLD_CANDIDATES = ("com", "net", "org", "edu", "gov", "info", "biz")


def _osa_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (optimal string alignment: adjacent transposition = 1)."""
    if a == b:
        return 0
    rows = len(a) + 1
    cols = len(b) + 1
    d = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        d[i][0] = i
    for j in range(cols):
        d[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def _close_enough(domain: str, candidate: str) -> int | None:
    """Return the edit distance if candidate is a plausible correction of domain, else None.

    One edit on the whole string is accepted. Two edits are accepted only when they are split
    across the two halves around the first dot (one in the name, one in the TLD), so that
    ``gmailer.com`` is not "corrected" to ``gmail.com`` while ``gnail.con`` is.
    """
    dist = _osa_distance(domain, candidate)
    if dist <= 1:
        return dist
    if dist == 2:
        name, _, tld = domain.partition(".")
        cname, _, ctld = candidate.partition(".")
        if _osa_distance(name, cname) <= 1 and _osa_distance(tld, ctld) <= 1:
            return dist
    return None


def suggest_domain(domain: str) -> str | None:
    """Return the likely intended domain for a misspelling (gmial.com -> gmail.com), else None.

    Never suggests anything for a domain that is itself a known provider. Unknown names shorter
    than four characters are left alone.
    """
    d = _clean(domain)
    name, dot, tld = d.partition(".")
    if not dot or not name or not tld or d in _known_domains():
        return None
    if len(name) >= 4:
        best: tuple[int, str] | None = None
        for candidate in _POPULAR_DOMAINS:
            dist = _close_enough(d, candidate)
            if dist is not None and (best is None or dist < best[0]):
                best = (dist, candidate)
        if best is not None:
            return best[1]
    last = d.rsplit(".", 1)[1]
    if len(last) >= 3 and last not in _VALID_TLDS:
        fixes = [t for t in _TLD_CANDIDATES if _osa_distance(last, t) == 1]
        if len(fixes) == 1:
            return d[: -len(last)] + fixes[0]
    return None


# ---------------------------------------------------------------------------------------------
# gibberish

_VOWELS = frozenset("aeiouy")
_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_LATIN = re.compile(r"[a-z]")


def _ascii_fold(text: str) -> str | None:
    """Lower-case and strip accents; None if a non-Latin letter remains."""
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )
    if any(c.isalpha() and not c.isascii() for c in folded):
        return None
    return folded


def _has_sequence(text: str, rows: tuple[str, ...], window: int) -> bool:
    for row in rows:
        for line in (row, row[::-1]):
            for i in range(len(line) - window + 1):
                if line[i : i + window] in text:
                    return True
    return False


def _max_consonant_run(letters: str) -> int:
    best = run = 0
    for c in letters:
        if c in _VOWELS:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


def _segment_score(text: str) -> float:
    letters = "".join(c for c in text if c.isalpha())
    digits = sum(c.isdigit() for c in text)
    total = len(letters) + digits
    score = 0.0
    if len(letters) >= 5:
        vowel_ratio = sum(c in _VOWELS for c in letters) / len(letters)
        if vowel_ratio < 0.15:
            score += 0.5
        elif vowel_ratio < 0.25:
            score += 0.2
        elif vowel_ratio > 0.8:
            score += 0.3
        run = _max_consonant_run(letters)
        if run >= 6:
            score += 0.5
        elif run == 5:
            score += 0.3
    if total >= 6 and len(set(text)) <= 2:
        score += 0.6
    if re.search(r"(.)\1{3,}", text):
        score += 0.5
    if _has_sequence(letters, _KEYBOARD_ROWS, 5):
        score += 0.6
    if _has_sequence(text, ("1234567890",), 5):
        score += 0.15
    if letters and digits:
        transitions = sum(a.isdigit() != b.isdigit() for a, b in zip(text, text[1:], strict=False))
        ratio = digits / total
        if transitions >= 4:
            score += 0.5
        elif transitions >= 3 and 0.3 <= ratio <= 0.7:
            score += 0.35
    return score


def gibberish_score(local: str) -> float:
    """Return 0.0 (natural) to 1.0 (random keyboard mash) for a local part.

    Heuristic on vowel ratio, consonant runs, keyboard rows, repeated characters and
    letter/digit interleaving. A trailing number (``jane1985``) and all-digit locals are not
    penalised. Scripts other than Latin score 0.0.
    """
    base = local.split("+", 1)[0]
    folded = _ascii_fold(base)
    if folded is None:
        return 0.0
    tokens = [t for t in re.split(r"[._\-]+", folded) if t]
    if not tokens:
        return 0.0
    candidates = ["".join(tokens)]
    candidates.extend(t for t in tokens if len(t) >= 5)
    score = max(_segment_score(c) for c in candidates)
    if all(c.isdigit() for c in candidates[0]):
        score = min(score, 0.15)
    return round(min(1.0, score), 3)


# ---------------------------------------------------------------------------------------------
# disposable lists


class DisposableLists:
    """Disposable, allow and strict lists; implements the StrictDomainLists protocol."""

    def __init__(
        self,
        disposable: Iterable[str] = (),
        allow: Iterable[str] = (),
        strict: Iterable[str] = (),
    ) -> None:
        """Start from the given sets (not the bundle); use load_bundled for the snapshot."""
        self._raw_disposable = _clean_all(disposable)
        self._raw_strict = _clean_all(strict)
        self._allow = _clean_all(allow)
        self._disposable = self._raw_disposable - self._allow - _free_providers()
        self._strict = self._raw_strict - self._disposable - self._allow - _free_providers()

    @classmethod
    def load_bundled(cls, *, strict: bool = False) -> DisposableLists:
        """Load the snapshot shipped in prebounce/data; the strict list only when asked."""
        disposable = _parse_domains(_read_data("disposable_primary.txt"))
        disposable += _parse_domains(_read_data("disposable_fakefilter.txt"))
        extra = _parse_domains(_read_data("disposable_strict.txt")) if strict else []
        return cls(disposable, _parse_domains(_read_data("allow.txt")), extra)

    @classmethod
    def load_refreshed(cls, store: Cache, *, strict: bool = False) -> DisposableLists:
        """Bundled snapshot merged with the lists saved by refresh_domain_lists, if any."""
        lists = cls.load_bundled(strict=strict)
        return lists.merge(
            _stored_domains(store, _KEY_DISPOSABLE),
            _stored_domains(store, _KEY_ALLOW),
            _stored_domains(store, _KEY_STRICT) if strict else (),
        )

    def disposable(self) -> frozenset[str]:
        return self._disposable

    def allow(self) -> frozenset[str]:
        return self._allow

    def strict(self) -> frozenset[str]:
        """Domains listed only by the strict source (not in disposable(), not allowed)."""
        return self._strict

    def is_disposable(self, domain: str, *, strict: bool = False) -> bool:
        """True if domain or any parent domain is listed and no allow entry covers it.

        With strict=True the strict list is consulted as well.
        """
        d = _clean(domain)
        if not d or d in _free_providers():
            return False
        return match_disposable(self, d, strict=strict) is not None

    def merge(
        self,
        disposable: Iterable[str] = (),
        allow: Iterable[str] = (),
        strict: Iterable[str] = (),
    ) -> DisposableLists:
        """Return a new instance with the extra entries added."""
        return DisposableLists(
            self._raw_disposable | _clean_all(disposable),
            self._allow | _clean_all(allow),
            self._raw_strict | _clean_all(strict),
        )


def match_disposable(lists: DomainLists, domain: str, *, strict: bool = False) -> str | None:
    """Return "core" or "strict" for the list that flags domain, or None if it is not flagged.

    The domain and each parent are checked; an allow entry anywhere in the chain wins. The strict
    list is consulted only when strict is true and lists implements StrictDomainLists.
    """
    labels = domain.lower().rstrip(".").split(".")
    chain = [".".join(labels[i:]) for i in range(max(1, len(labels) - 1))]
    allow = lists.allow()
    if any(name in allow for name in chain):
        return None
    disposable = lists.disposable()
    if any(name in disposable for name in chain):
        return "core"
    if strict and isinstance(lists, StrictDomainLists):
        extra = lists.strict()
        if any(name in extra for name in chain):
            return "strict"
    return None


# ---------------------------------------------------------------------------------------------
# refresh


def _stored_domains(store: Cache, key: str) -> frozenset[str]:
    value = store.get(key)
    if isinstance(value, dict):
        domains = value.get("domains")
        if isinstance(domains, list):
            return frozenset(str(x) for x in domains)
    return frozenset()


def _valid_hostname(name: str) -> bool:
    return len(name) <= 253 and _HOSTNAME.fullmatch(name) is not None


def _parse_source(text: str) -> tuple[frozenset[str], int, int]:
    """Return (valid domains, entry count, invalid count) for downloaded list text."""
    entries = [_clean(e) for e in _parse_domains(text)]
    valid = frozenset(e for e in entries if _valid_hostname(e))
    return valid, len(entries), len(entries) - sum(1 for e in entries if _valid_hostname(e))


def refresh_domain_lists(
    fetch: Callable[[str], str], store: Cache, *, strict: bool = False
) -> RefreshReport:
    """Fetch upstream list sources via fetch(url) -> text and save the merged result in store.

    The strict source (about 1.5 MB) is fetched only when strict is true; domains_added and
    domains_total count the core disposable list only.

    The library itself never opens sockets here; the host supplies fetch. A source is rejected
    (and its previously stored copy kept) when the fetch fails, when it parses to nothing, when
    it has fewer than half the domains of the stored copy, or when more than 1% of its entries
    are not valid hostnames.
    """
    errors: list[str] = []
    accepted = 0
    sets: dict[str, frozenset[str]] = {}
    for name, url, kind in _SOURCES:
        if kind == "strict" and not strict:
            continue
        key = f"{_KEY_PREFIX}source:{name}"
        previous = _stored_domains(store, key)
        try:
            text = fetch(url)
        except Exception as exc:  # noqa: BLE001 - host fetch may raise anything
            errors.append(f"{name}: fetch failed: {exc}")
            sets[name] = previous
            continue
        valid, total, invalid = _parse_source(text)
        if total == 0 or not valid:
            errors.append(f"{name}: empty list rejected")
        elif invalid / total > _MAX_INVALID_RATIO:
            errors.append(f"{name}: {invalid} of {total} entries are not valid hostnames")
        elif previous and len(valid) < len(previous) * _MAX_SHRINK_RATIO:
            errors.append(f"{name}: shrank from {len(previous)} to {len(valid)} domains")
        else:
            store.set(
                key,
                {
                    "domains": sorted(valid),
                    "count": len(valid),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                },
                _STORE_TTL,
            )
            sets[name] = valid
            accepted += 1
            continue
        sets[name] = previous
    previous_merged = _stored_domains(store, _KEY_DISPOSABLE)
    if accepted == 0:
        return RefreshReport(0, 0, len(previous_merged), tuple(errors))
    allow = sets["allow"]
    merged = (sets["primary"] | sets["fakefilter"]) - allow - _free_providers()
    store.set(_KEY_DISPOSABLE, {"domains": sorted(merged)}, _STORE_TTL)
    store.set(_KEY_ALLOW, {"domains": sorted(allow)}, _STORE_TTL)
    if strict:
        extra = sets["strict"] - merged - allow - _free_providers()
        store.set(_KEY_STRICT, {"domains": sorted(extra)}, _STORE_TTL)
    return RefreshReport(accepted, len(merged - previous_merged), len(merged), tuple(errors))


__all__ = [
    "DisposableLists",
    "RefreshReport",
    "gibberish_score",
    "is_free_provider",
    "is_role",
    "match_disposable",
    "refresh_domain_lists",
    "suggest_domain",
]
