#!/bin/zsh
set -euo pipefail

ROOT=${0:A:h:h}
REPORTS_DIR="$ROOT/reports"
LOG_DIR="$REPORTS_DIR/logs"
TODAY=$(date '+%Y-%m-%d')
LOG_FILE="$LOG_DIR/daily-$TODAY.log"

mkdir -p "$LOG_DIR"

log() {
  local timestamp
  timestamp=$(date '+%Y-%m-%d %H:%M:%S %Z')
  print -r -- "[$timestamp] $*" | tee -a "$LOG_FILE"
}

capture_command() {
  local output exit_code
  set +e
  output="$("$@" 2>&1)"
  exit_code=$?
  set -e
  if [[ -n "$output" ]]; then
    print -r -- "$output" | tee -a "$LOG_FILE"
  fi
  return "$exit_code"
}

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
if [[ -z "$PYTHON_BIN" ]]; then
  log "未找到 python3，停止执行。"
  exit 127
fi

log "开始执行 XHS 日报本地任务。"
log "Python: $PYTHON_BIN"

auth_attempt=1
auth_ok=0
while (( auth_attempt <= 2 )); do
  if capture_command "$PYTHON_BIN" -B "$ROOT/xhs_auth_refresh.py" --mode check; then
    auth_ok=1
    break
  fi
  check_status=$?
  check_output=$(tail -n 20 "$LOG_FILE")
  if [[ "$check_output" == *"network_error:"* && "$auth_attempt" -lt 2 ]]; then
    log "检测到网络异常，30 秒后重试登录检查。"
    sleep 30
    auth_attempt=$((auth_attempt + 1))
    continue
  fi
  break
done

if (( auth_ok == 1 )); then
  log "登录检查通过，开始生成日报。"
else
  if [[ "$check_output" == *"network_error:"* ]]; then
    log "当前主机无法访问小红书接口，已停止本次日报。"
    exit 20
  fi
  log "登录态不可用，请在宿主机执行: python3 xhs_auth_refresh.py --mode qr"
  exit "${check_status:-1}"
fi

send_args=()
if [[ "${XHS_SEND_FEISHU:-0}" == "1" ]]; then
  send_args=(--send-feishu)
  log "已启用飞书发送。"
fi

if capture_command "$PYTHON_BIN" -B "$ROOT/run_daily_digest.py" "${send_args[@]}"; then
  markdown_path="$REPORTS_DIR/$TODAY.md"
  json_path="$REPORTS_DIR/$TODAY.json"
  if [[ -s "$markdown_path" && -s "$json_path" ]]; then
    log "日报生成完成: $markdown_path"
    log "结构化结果: $json_path"
    exit 0
  fi
  log "日报命令返回成功，但缺少预期输出文件。"
  exit 30
fi

digest_status=$?
log "日报生成失败，退出码: $digest_status"
exit "$digest_status"
