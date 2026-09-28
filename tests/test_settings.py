import pytest

from prebounce import ConfigurationError, ProxyConfig, Settings


def test_defaults_are_safe() -> None:
    s = Settings()
    assert not s.dns_enabled and not s.smtp_enabled
    assert s.cache_ttl["deliverable"] == 30 * 86400
    assert s.cache_ttl["unknown"] == 86400


def test_from_env_parses_values() -> None:
    env = {
        "PREBOUNCE_DNS_ENABLED": "true",
        "PREBOUNCE_SMTP_ENABLED": "1",
        "PREBOUNCE_SMTP_HELO": "mail.example.com",
        "PREBOUNCE_SMTP_MAIL_FROM": "probe@example.com",
        "PREBOUNCE_PROBE_TIMEOUT": "7.5",
        "PREBOUNCE_MAX_GREYLIST_ATTEMPTS": "5",
        "PREBOUNCE_CATCH_ALL_CHECK": "off",
        "PREBOUNCE_BLOCKLIST_ZONES": "a.example, b.example",
        "PREBOUNCE_CACHE_TTL": '{"risky": 60}',
    }
    s = Settings.from_env(env)
    assert s.smtp_enabled and s.dns_enabled and not s.catch_all_check
    assert s.probe_timeout == 7.5 and s.max_greylist_attempts == 5
    assert s.blocklist_zones == ("a.example", "b.example")
    assert s.cache_ttl["risky"] == 60 and s.cache_ttl["domain"] == 86400


def test_from_env_proxies_and_prefix() -> None:
    env = {
        "X_DNS_ENABLED": "yes",
        "X_SMTP_ENABLED": "yes",
        "X_SMTP_PROXIES": '[{"url":"socks5://p:1080","helo":"h.example","mail_from":"a@h.example",'
        '"providers":["google"]}]',
    }
    s = Settings.from_env(env, prefix="X_")
    expected = ProxyConfig("socks5://p:1080", "h.example", "a@h.example", ("google",))
    assert s.smtp_proxies == (expected,)


def test_from_env_reads_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREBOUNCE_DNS_ENABLED", "1")
    assert Settings.from_env().dns_enabled


@pytest.mark.parametrize(
    "env",
    [
        {"PREBOUNCE_DNS_ENABLED": "maybe"},
        {"PREBOUNCE_MAX_GREYLIST_ATTEMPTS": "x"},
        {"PREBOUNCE_PROBE_TIMEOUT": "x"},
        {"PREBOUNCE_SMTP_PROXIES": "not json"},
        {"PREBOUNCE_SMTP_PROXIES": '{"a": 1}'},
        {"PREBOUNCE_SMTP_PROXIES": '[{"url": "u"}]'},
        {"PREBOUNCE_CACHE_TTL": '{"bogus": 1}'},
        {"PREBOUNCE_SMTP_ENABLED": "1", "PREBOUNCE_DNS_ENABLED": "1"},
        {"PREBOUNCE_BLOCKLIST_ZONES": "z.example"},
        {"PREBOUNCE_PROBE_TIMEOUT": "0"},
    ],
)
def test_invalid_configuration_raises(env: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env(env)


def test_smtp_with_proxies_only_is_valid() -> None:
    proxy = ProxyConfig("socks5://p:1", "h.example", "a@h.example")
    assert Settings(dns_enabled=True, smtp_enabled=True, smtp_proxies=(proxy,)).smtp_enabled
