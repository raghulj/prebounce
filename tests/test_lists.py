"""Tests for prebounce.lists.

Typo vectors are adapted from mailcheck's spec (MIT, https://github.com/mailcheck/mailcheck):
gmailc.om, gnail.con, yaho.com, hotmial.com and friends. Role, gibberish and disposable cases are
original. Nothing here touches the network.
"""

from __future__ import annotations

from typing import Any

import pytest

from prebounce import lists
from prebounce.cache import MemoryCache
from prebounce.lists import (
    DisposableLists,
    gibberish_score,
    is_free_provider,
    is_role,
    refresh_domain_lists,
    suggest_domain,
)

# ---------------------------------------------------------------- role


@pytest.mark.parametrize(
    "local",
    [
        "admin", "info", "sales", "support", "noreply", "no-reply", "no_reply", "postmaster",
        "abuse", "webmaster", "hostmaster", "billing", "contact", "hello", "office", "team",
        "marketing", "jobs", "careers", "hr", "security", "privacy", "Info", "SALES+eu",
        "  support  ",
    ],
)  # fmt: skip
def test_role_addresses(local: str) -> None:
    assert is_role(local)


@pytest.mark.parametrize(
    "local", ["john", "john.smith", "info.john", "sales.rep", "adminx", "maria+admin", ""]
)
def test_non_role_addresses(local: str) -> None:
    assert not is_role(local)


# ---------------------------------------------------------------- free providers


@pytest.mark.parametrize(
    "domain",
    [
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "outlook.com", "hotmail.com",
        "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mac.com", "proton.me",
        "protonmail.com", "gmx.de", "gmx.net", "web.de", "mail.ru", "yandex.ru", "zoho.com",
        "fastmail.com", "tutanota.com", "qq.com", "163.com", "126.com", "naver.com", "GMAIL.COM",
    ],
)  # fmt: skip
def test_free_providers(domain: str) -> None:
    assert is_free_provider(domain)


@pytest.mark.parametrize("domain", ["example.com", "mail.gmail.com", "acme.io", ""])
def test_not_free_providers(domain: str) -> None:
    assert not is_free_provider(domain)


def test_free_provider_list_is_curated_size() -> None:
    assert 80 <= len(lists._free_providers()) <= 200


# ---------------------------------------------------------------- typo suggestions


@pytest.mark.parametrize(
    ("typo", "expected"),
    [
        ("gmailc.om", "gmail.com"),
        ("gnail.con", "gmail.com"),
        ("gmial.com", "gmail.com"),
        ("gmai.com", "gmail.com"),
        ("gmail.con", "gmail.com"),
        ("gmail.co", "gmail.com"),
        ("yaho.com", "yahoo.com"),
        ("yahooo.com", "yahoo.com"),
        ("yahoo.con", "yahoo.com"),
        ("hotmial.com", "hotmail.com"),
        ("hotmail.con", "hotmail.com"),
        ("hotnail.com", "hotmail.com"),
        ("outlok.com", "outlook.com"),
        ("icloud.con", "icloud.com"),
        ("iclould.com", "icloud.com"),
        ("protonmial.com", "protonmail.com"),
        ("GMIAL.COM", "gmail.com"),
        ("example.con", "example.com"),
        ("example.cim", "example.com"),
        ("company.ent", "company.net"),
        ("company.ogr", "company.org"),
    ],
)
def test_typo_suggestions(typo: str, expected: str) -> None:
    assert suggest_domain(typo) == expected


@pytest.mark.parametrize(
    "domain",
    [
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com",
        "live.com", "msn.com", "mail.com", "gmx.com", "gmx.net", "yahoo.co.uk", "googlemail.com",
        "att.net", "att.com", "example.com", "company.co", "gmailer.com", "me.co", "acme.io",
        "example.co.uk", "wiki.cam", "startup.ai", "site.cm", "", "nodot", "a.b",
    ],
)  # fmt: skip
def test_no_false_suggestion(domain: str) -> None:
    assert suggest_domain(domain) is None


def test_osa_distance_counts_transposition_as_one() -> None:
    assert lists._osa_distance("gmial", "gmail") == 1
    assert lists._osa_distance("kitten", "sitting") == 3
    assert lists._osa_distance("", "abc") == 3
    assert lists._osa_distance("same", "same") == 0


# ---------------------------------------------------------------- gibberish


@pytest.mark.parametrize(
    "local",
    [
        "john.smith", "mary_jones", "krzysztof", "schwarzenegger", "wojciechowski", "christopher",
        "m.rodriguez", "alexandra", "nguyen.tran", "o.brien", "mcdonald", "szymanski",
        "strzelecki", "jane1985", "jsmith", "john.doe87", "1234567", "sarah+news", "josé",
        "李雷", "kowalczyk", "info", "",
    ],
)  # fmt: skip
def test_real_names_score_low(local: str) -> None:
    assert gibberish_score(local) < 0.3


@pytest.mark.parametrize(
    "local",
    [
        "xkqzjwvbn", "asdfghjkl", "qwertyuiop", "zxcvbnm123", "a8f3k2j9d1x", "bcdfghjklm",
        "aaaaaaaaaa", "xk7q2z9w", "x8k2m9q4z7", "hgfdsapoiuy",
    ],
)  # fmt: skip
def test_random_strings_score_high(local: str) -> None:
    assert gibberish_score(local) >= 0.5


def test_gibberish_score_is_bounded() -> None:
    for value in ("", "a", "zzzzzzzzzzzzzzzz", "q1w2e3r4t5y6", "John Smith"):
        assert 0.0 <= gibberish_score(value) <= 1.0


# ---------------------------------------------------------------- disposable


def test_disposable_exact_and_subdomain_match() -> None:
    dl = DisposableLists(disposable=["tempmail.example", "Burner.Test."])
    assert dl.is_disposable("tempmail.example")
    assert dl.is_disposable("TEMPMAIL.example")
    assert dl.is_disposable("a.b.tempmail.example")
    assert dl.is_disposable("burner.test")
    assert not dl.is_disposable("mytempmail.example")
    assert not dl.is_disposable("example")
    assert not dl.is_disposable("")


def test_parent_walk_stops_at_two_labels() -> None:
    dl = DisposableLists(disposable=["com", "co.uk"])
    assert not dl.is_disposable("anything.com")
    assert dl.is_disposable("x.co.uk")


def test_allow_beats_disposable() -> None:
    dl = DisposableLists(
        disposable=["shared.example", "x.shared.example"], allow=["shared.example"]
    )
    assert not dl.is_disposable("shared.example")
    assert not dl.is_disposable("x.shared.example")
    assert "shared.example" not in dl.disposable()
    assert dl.allow() == frozenset({"shared.example"})


def test_allow_on_parent_covers_subdomain() -> None:
    dl = DisposableLists(disposable=["a.trusted.example"], allow=["trusted.example"])
    assert not dl.is_disposable("a.trusted.example")


@pytest.mark.parametrize("domain", ["gmail.com", "outlook.com", "yahoo.com", "hotmail.com"])
def test_free_providers_never_disposable(domain: str) -> None:
    dl = DisposableLists(disposable=[domain])
    assert not dl.is_disposable(domain)
    assert domain not in dl.disposable()


def test_merge_unions_disposable_and_subtracts_allow() -> None:
    base = DisposableLists(disposable=["a.example", "b.example"], allow=["c.example"])
    merged = base.merge(disposable=["c.example", "d.example"], allow=["b.example"])
    assert merged.disposable() == frozenset({"a.example", "d.example"})
    assert merged.allow() == frozenset({"b.example", "c.example"})
    assert base.disposable() == frozenset({"a.example", "b.example"})


def test_idna_entries_are_normalised() -> None:
    dl = DisposableLists(disposable=["bücher-mail.example"])
    assert dl.is_disposable("xn--bcher-mail-9db.example")
    assert dl.is_disposable("BÜCHER-MAIL.example")


def test_bundled_lists_are_non_trivial() -> None:
    dl = DisposableLists.load_bundled()
    assert len(dl.disposable()) > 5000
    assert len(dl.allow()) > 500
    assert dl.is_disposable("mailinator.com")
    assert dl.is_disposable("sub.mailinator.com")
    assert not dl.is_disposable("gmail.com")
    assert not dl.is_disposable("outlook.com")
    assert not dl.is_disposable("yahoo.com")
    assert not (dl.disposable() & dl.allow())
    assert not (dl.disposable() & lists._free_providers())


def test_bundled_comments_are_stripped() -> None:
    dl = DisposableLists.load_bundled()
    assert not any(d.startswith("#") or " " in d for d in dl.disposable() | dl.allow())


# ---------------------------------------------------------------- refresh

URLS = [source[1] for source in lists._SOURCES]


def _fake_fetch(texts: dict[str, str]) -> Any:
    def fetch(url: str) -> str:
        if url not in texts:
            raise OSError("offline")
        return texts[url]

    return fetch


def _domains(prefix: str, count: int) -> str:
    return "# header\n" + "\n".join(f"{prefix}{i}.example" for i in range(count)) + "\n"


def _good_texts(count: int = 100) -> dict[str, str]:
    return {
        URLS[0]: _domains("p", count),
        URLS[1]: _domains("f", count) + "gmail.com  # inline\n",
        URLS[2]: "p0.example\n",
    }


def test_refresh_stores_merged_lists() -> None:
    store = MemoryCache()
    report = refresh_domain_lists(_fake_fetch(_good_texts()), store)
    assert report.source_count == 3
    assert report.errors == ()
    assert report.domains_total == 199  # 200 minus allowed p0, gmail.com excluded as free
    assert report.domains_added == 199
    merged = store.get("prebounce:lists:v1:disposable")
    assert merged is not None
    assert "p1.example" in merged["domains"]
    assert "p0.example" not in merged["domains"]
    assert store.get("prebounce:lists:v1:allow") == {"domains": ["p0.example"]}
    source = store.get("prebounce:lists:v1:source:primary")
    assert source is not None and source["count"] == 100 and "fetched_at" in source


def test_refresh_is_readable_through_load_refreshed() -> None:
    store = MemoryCache()
    refresh_domain_lists(_fake_fetch(_good_texts()), store)
    dl = DisposableLists.load_refreshed(store)
    assert dl.is_disposable("f5.example")
    assert dl.is_disposable("mailinator.com")


def test_refresh_second_run_adds_only_new_domains() -> None:
    store = MemoryCache()
    refresh_domain_lists(_fake_fetch(_good_texts(100)), store)
    report = refresh_domain_lists(_fake_fetch(_good_texts(110)), store)
    assert report.domains_added == 20
    assert report.domains_total == 219


def test_refresh_rejects_empty_source_and_keeps_previous() -> None:
    store = MemoryCache()
    refresh_domain_lists(_fake_fetch(_good_texts()), store)
    texts = _good_texts()
    texts[URLS[0]] = "# only a comment\n\n"
    report = refresh_domain_lists(_fake_fetch(texts), store)
    assert report.source_count == 2
    assert any("primary" in e and "empty" in e for e in report.errors)
    merged = store.get("prebounce:lists:v1:disposable")
    assert merged is not None
    assert "p1.example" in merged["domains"]


def test_refresh_rejects_shrink_over_half() -> None:
    store = MemoryCache()
    refresh_domain_lists(_fake_fetch(_good_texts(100)), store)
    texts = _good_texts(100)
    texts[URLS[1]] = _domains("f", 49)
    report = refresh_domain_lists(_fake_fetch(texts), store)
    assert any("shrank" in e and "fakefilter" in e for e in report.errors)
    kept = store.get("prebounce:lists:v1:source:fakefilter")
    assert kept is not None
    assert kept["count"] == 101
    texts[URLS[1]] = _domains("f", 51)
    assert refresh_domain_lists(_fake_fetch(texts), store).errors == ()


def test_refresh_rejects_too_many_invalid_hostnames() -> None:
    store = MemoryCache()
    texts = _good_texts()
    texts[URLS[0]] = _domains("p", 97) + "not a host\n-bad-.com\nnodot\n"
    report = refresh_domain_lists(_fake_fetch(texts), store)
    assert report.source_count == 2
    assert any("not valid hostnames" in e for e in report.errors)
    assert store.get("prebounce:lists:v1:source:primary") is None


def test_refresh_tolerates_a_stray_invalid_line() -> None:
    store = MemoryCache()
    texts = _good_texts(200)
    texts[URLS[0]] += "-bad-.com\n"
    report = refresh_domain_lists(_fake_fetch(texts), store)
    assert report.source_count == 3


def test_refresh_fetch_failure_is_reported_not_raised() -> None:
    store = MemoryCache()
    texts = _good_texts()
    del texts[URLS[1]]
    report = refresh_domain_lists(_fake_fetch(texts), store)
    assert report.source_count == 2
    assert any("fakefilter" in e and "fetch failed" in e for e in report.errors)
    assert store.get("prebounce:lists:v1:disposable") is not None


def test_refresh_all_failing_writes_nothing() -> None:
    store = MemoryCache()
    report = refresh_domain_lists(_fake_fetch({}), store)
    assert report.source_count == 0
    assert report.domains_added == 0
    assert report.domains_total == 0
    assert len(report.errors) == 3
    assert len(store) == 0
