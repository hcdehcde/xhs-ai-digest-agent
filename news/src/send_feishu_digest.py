#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent
FEISHU_ENV_PATH = ROOT / "feishu_app.env"
SENT_STATE_PATH = ROOT / "reports" / ".feishu_sent.json"


def load_feishu_config(path: Path) -> Dict[str, str]:
    env = dotenv_values(path)
    return {
        "app_id": (env.get("APP_ID") or "").strip(),
        "app_secret": (env.get("APP_SECRET") or "").strip(),
        "receive_id_type": (env.get("RECEIVE_ID_TYPE") or "chat_id").strip(),
        "receive_id": (
            env.get("RECEIVE_ID")
            or env.get("OPEN_ID")
            or env.get("USER_ID")
            or env.get("CHAT_ID")
            or ""
        ).strip(),
    }


def http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    request_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        request_headers.update(headers)
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=request_headers, method="POST")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    res = http_post_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    if res.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {res}")
    return res["tenant_access_token"]


def build_text_digest(markdown_path: Path) -> str:
    lines = [line.rstrip() for line in markdown_path.read_text(encoding="utf-8").splitlines()]
    filtered = [line for line in lines if line.strip()]
    return "\n".join(filtered)


def load_sent_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_sent_state(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def send_text_message(token: str, receive_id_type: str, receive_id: str, text: str) -> Dict[str, Any]:
    return http_post_json(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
        {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send daily digest to Feishu")
    parser.add_argument("--digest", required=True, help="Path to markdown digest")
    parser.add_argument("--config", default=str(FEISHU_ENV_PATH))
    args = parser.parse_args()

    config = load_feishu_config(Path(args.config))
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise SystemExit(f"缺少飞书配置: {', '.join(missing)}")

    digest_path = Path(args.digest)
    if not digest_path.exists():
        raise SystemExit(f"日报文件不存在: {digest_path}")

    try:
        token = get_tenant_access_token(config["app_id"], config["app_secret"])
        text = build_text_digest(digest_path)
        digest_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        date_key = digest_path.stem
        state = load_sent_state(SENT_STATE_PATH)
        if state.get("date") == date_key and state.get("digest_hash") == digest_hash:
            print("status=skipped")
            print("reason=already_sent")
            return
        res = send_text_message(token, config["receive_id_type"], config["receive_id"], text)
    except HTTPError as exc:
        raise SystemExit(f"飞书请求失败: HTTP {exc.code}") from exc
    except URLError as exc:
        raise SystemExit(f"飞书网络请求失败: {exc.reason}") from exc

    if res.get("code") != 0:
        raise SystemExit(f"飞书发送失败: {res}")

    write_sent_state(
        SENT_STATE_PATH,
        {
            "date": date_key,
            "digest_hash": digest_hash,
            "message_id": res.get("data", {}).get("message_id", ""),
        },
    )
    print("status=ok")
    print(f"message_id={res.get('data', {}).get('message_id', '')}")


if __name__ == "__main__":
    main()
