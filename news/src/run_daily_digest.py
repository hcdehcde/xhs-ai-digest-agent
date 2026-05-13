#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from xhs_auth_common import is_auth_error, is_network_error
from xhs_digest_collect import REPORTS_DIR, ROOT, SPIDER_ROOT, run_digest


LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def write_failure_artifacts(
    markdown_path: Path,
    json_path: Path,
    *,
    date_str: str,
    reason: str,
    message: str,
) -> None:
    failure_payload = {
        "date": date_str,
        "status": "failed",
        "reason": reason,
        "message": message,
    }
    json_path.write_text(json.dumps(failure_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# XHS AI 日报",
        "",
        "## 状态",
        "- 本次自动任务未成功生成日报",
        f"- 原因：{reason}",
        f"- 详情：{message}",
        "",
    ]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the formal Xiaohongshu daily digest")
    parser.add_argument("--rules", default=str(ROOT / "xhs-digest-agent.rules.yaml"))
    parser.add_argument("--cookie-env", default=str(SPIDER_ROOT / ".env"))
    parser.add_argument("--per-author", type=int, default=2)
    parser.add_argument("--detail-limit", type=int, default=50)
    parser.add_argument("--send-feishu", action="store_true")
    parser.add_argument("--date", help="Run digest for a specific local date, format: YYYY-MM-DD")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)
    if args.date:
        reference_dt = datetime.strptime(args.date, "%Y-%m-%d").date()
        date_str = args.date
    else:
        reference_dt = datetime.now(LOCAL_TZ).date()
        date_str = reference_dt.strftime("%Y-%m-%d")
    markdown_path = REPORTS_DIR / f"{date_str}.md"
    json_path = REPORTS_DIR / f"{date_str}.json"

    try:
        result = run_digest(
            rules_path=Path(args.rules),
            cookie_env_path=Path(args.cookie_env),
            per_author=args.per_author,
            detail_limit=args.detail_limit,
            markdown_path=markdown_path,
            json_path=json_path,
            reference_date=reference_dt,
        )
    except Exception as exc:
        message = str(exc)
        reason = "runtime_error"
        next_step = None
        if is_network_error(message) or "当前环境无法访问小红书接口" in message:
            reason = "network_unavailable"
            next_step = "请先检查当前机器的 DNS 或网络连通性，再重新运行日报任务"
        elif "Cookie invalid or expired" in message or is_auth_error(message):
            reason = "auth_required"
            next_step = "python3 xhs_auth_refresh.py --mode qr"

        write_failure_artifacts(
            markdown_path,
            json_path,
            date_str=date_str,
            reason=reason,
            message=message,
        )

        print(f"date={date_str}")
        print("status=failed")
        print(f"reason={reason}")
        if next_step:
            print(f"next_step={next_step}")
        print(f"message={message}")
        raise SystemExit(1)

    digest_count = len(result["digest_items"])
    print(f"date={date_str}")
    print("status=ok" if digest_count > 0 else "status=no_digest")
    print(f"markdown={markdown_path}")
    print(f"json={json_path}")
    print(f"digest_items={digest_count}")
    print(f"author_fetch_errors={result['summary'].get('author_fetch_errors', 0)}")
    if digest_count == 0:
        print("message=今天没有符合规则的日报内容")
        return

    if args.send_feishu:
        send_cmd = [sys.executable, str(ROOT / "send_feishu_digest.py"), "--digest", str(markdown_path)]
        subprocess.run(send_cmd, check=True)


if __name__ == "__main__":
    main()
