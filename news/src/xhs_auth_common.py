#!/usr/bin/env python3
from __future__ import annotations


NETWORK_ERROR_HINTS = (
    "NameResolutionError",
    "Failed to resolve",
    "nodename nor servname provided",
    "Temporary failure in name resolution",
    "Max retries exceeded",
    "Connection refused",
    "Connection aborted",
    "Connection reset",
    "ConnectTimeout",
    "ReadTimeout",
    "ProxyError",
    "SSLError",
)

AUTH_ERROR_HINTS = (
    "登录已过期",
    "登录状态异常",
    "登录失效",
    "账号状态异常",
    "cookie invalid or expired",
    "Please login",
    "login",
    "not login",
)


def is_network_error(message: str) -> bool:
    text = (message or "").strip()
    return any(hint in text for hint in NETWORK_ERROR_HINTS)


def is_auth_error(message: str) -> bool:
    text = (message or "").strip().lower()
    return any(hint.lower() in text for hint in AUTH_ERROR_HINTS)
