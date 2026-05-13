#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import io
from pathlib import Path

from dotenv import dotenv_values
import qrcode

from xhs_auth_common import is_network_error

ROOT = Path(__file__).resolve().parent
SPIDER_ROOT = ROOT / "Spider_XHS"
ENV_PATH = SPIDER_ROOT / ".env"
QR_PATH = ROOT / "reports" / "xhs-login-qr.png"

import os
import sys

os.chdir(SPIDER_ROOT)
sys.path.insert(0, str(SPIDER_ROOT))

from apis.xhs_pc_apis import XHS_Apis  # noqa: E402
from apis.xhs_pc_login_apis import XHSLoginApi  # noqa: E402


def load_cookies() -> str:
    env = dotenv_values(ENV_PATH)
    return env.get("COOKIES", "") or ""


def write_cookies(cookies_str: str) -> None:
    ENV_PATH.write_text(f"COOKIES='{cookies_str.strip()}'\n", encoding="utf-8")


def validate_cookie(cookies_str: str) -> tuple[bool, str]:
    if not cookies_str:
        return False, "empty_cookie"
    api = XHS_Apis()
    ok, msg, _ = api.get_user_self_info(cookies_str)
    if not ok and is_network_error(msg):
        return False, f"network_error: {msg}"
    return ok, msg


def build_qr(verify_url: str) -> qrcode.QRCode:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verify_url)
    qr.make(fit=True)
    return qr


def save_qr_image(verify_url: str) -> Path:
    QR_PATH.parent.mkdir(exist_ok=True)
    qr = build_qr(verify_url)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(QR_PATH)
    return QR_PATH


def print_qr_ascii(verify_url: str) -> None:
    qr = build_qr(verify_url)
    buffer = io.StringIO()
    qr.print_ascii(out=buffer)
    print("未检测到 Pillow，已回退为终端二维码：")
    print(buffer.getvalue())
    print(f"登录链接: {verify_url}")


async def refresh_via_qr(timeout_sec: int = 180) -> tuple[bool, str]:
    login_api = XHSLoginApi()
    cookies = await login_api.xhsGenerateInitCookies(headless=True)
    success, msg, qrcode_dict = await login_api.xhsGenerateQRcode(cookies)
    if not success:
        return False, msg

    verify_url = qrcode_dict["verify_url"]
    try:
        qr_path = save_qr_image(verify_url)
        print(f"二维码已生成: {qr_path}")
    except ModuleNotFoundError as exc:
        if exc.name != "PIL":
            raise
        print_qr_ascii(verify_url)
    print("请用小红书 App 扫码并确认登录。")

    for _ in range(timeout_sec):
        success, msg, res = await login_api.xhsCheckQRCodeLogin(
            qrcode_dict["qr_id"],
            qrcode_dict["code"],
            qrcode_dict["cookies"],
        )
        cookies_str = res.get("cookies_str")
        if success and cookies_str:
            write_cookies(cookies_str)
            return True, "qr_login_success"
        await asyncio.sleep(1)
    return False, "qr_login_timeout"


async def refresh_via_phone(phone: str) -> tuple[bool, str]:
    login_api = XHSLoginApi()
    cookies = await login_api.xhsGenerateInitCookies(headless=True)
    success, msg = await login_api.xhsGeneratePhoneVerificationCode(phone, cookies)
    if not success:
        return False, msg

    code = input("请输入短信验证码: ").strip()
    success, msg, mobile_token = await login_api.xhsCheckPhoneVerificationCode(phone, code, cookies)
    if not success:
        return False, msg

    success, msg, cookies_str = await login_api.xhsPhoneVerificationCodeLogin(mobile_token, phone, cookies)
    if not success or not cookies_str:
        return False, msg

    write_cookies(cookies_str)
    return True, "phone_login_success"


async def main_async() -> int:
    parser = argparse.ArgumentParser(description="Refresh Xiaohongshu auth for Spider_XHS")
    parser.add_argument("--mode", choices=["check", "qr", "phone"], default="check")
    parser.add_argument("--phone", default="")
    args = parser.parse_args()

    if args.mode == "check":
        ok, msg = validate_cookie(load_cookies())
        print(f"cookie_ok={ok}")
        print(f"msg={msg}")
        return 0 if ok else 1

    if args.mode == "qr":
        ok, msg = await refresh_via_qr()
        print(f"refresh_ok={ok}")
        print(f"msg={msg}")
        return 0 if ok else 1

    if not args.phone:
        print("phone 模式需要 --phone")
        return 1

    ok, msg = await refresh_via_phone(args.phone)
    print(f"refresh_ok={ok}")
    print(f"msg={msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
