"""Concrete SmtpTransport implementations."""

from __future__ import annotations

from prebounce.types import SmtpReply


class SocketTransport:
    """Direct TCP connection using the standard library."""

    def __init__(self) -> None:
        raise NotImplementedError

    def connect(self, host: str, port: int, timeout: float) -> SmtpReply:
        raise NotImplementedError

    def send(self, line: str) -> SmtpReply:
        raise NotImplementedError

    def starttls(self, server_hostname: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SocksTransport:
    """Connection through a SOCKS5 proxy (requires the socks extra)."""

    def __init__(self, proxy_url: str) -> None:
        raise NotImplementedError

    def connect(self, host: str, port: int, timeout: float) -> SmtpReply:
        raise NotImplementedError

    def send(self, line: str) -> SmtpReply:
        raise NotImplementedError

    def starttls(self, server_hostname: str) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
