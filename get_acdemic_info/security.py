"""Network safety checks for user-supplied academic source URLs."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


def validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("仅支持 http:// 或 https:// 学术来源")
    if not parsed.hostname:
        raise UnsafeUrlError("URL 缺少有效域名")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URL 不允许包含用户名或密码")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise UnsafeUrlError("不允许访问本机或局域网地址")

    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"无法解析目标域名: {hostname}") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise UnsafeUrlError("不允许访问内网、回环或保留地址")

    return parsed.geturl()
