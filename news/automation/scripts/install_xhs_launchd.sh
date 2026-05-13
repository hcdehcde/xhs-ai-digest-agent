#!/bin/zsh
set -euo pipefail

ROOT=${0:A:h:h}
PLIST_ID="com.codex.xhs-digest"
TEMPLATE="$ROOT/launchd/$PLIST_ID.plist"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_ID.plist"
HOUR="${1:-21}"
MINUTE="${2:-0}"

case "$HOUR" in
  ''|*[!0-9]*)
    print "Hour 必须是 0-23 的整数。"
    exit 1
    ;;
esac

case "$MINUTE" in
  ''|*[!0-9]*)
    print "Minute 必须是 0-59 的整数。"
    exit 1
    ;;
esac

if (( HOUR < 0 || HOUR > 23 )); then
  print "Hour 必须在 0-23 之间。"
  exit 1
fi

if (( MINUTE < 0 || MINUTE > 59 )); then
  print "Minute 必须在 0-59 之间。"
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  print "缺少模板文件: $TEMPLATE"
  exit 1
fi

mkdir -p "$TARGET_DIR" "$ROOT/reports/logs"

sed \
  -e "s|__ROOT__|$ROOT|g" \
  "$TEMPLATE" > "$TARGET_PLIST"

/usr/libexec/PlistBuddy -c "Set :StartCalendarInterval:Hour $HOUR" "$TARGET_PLIST"
/usr/libexec/PlistBuddy -c "Set :StartCalendarInterval:Minute $MINUTE" "$TARGET_PLIST"

chmod 644 "$TARGET_PLIST"

launchctl bootout "gui/$UID/$PLIST_ID" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$TARGET_PLIST"
launchctl enable "gui/$UID/$PLIST_ID"

print "已安装 launchd 任务: $PLIST_ID"
print "计划时间: $(printf '%02d:%02d' "$HOUR" "$MINUTE")"
print "任务文件: $TARGET_PLIST"
print "查看状态: launchctl print gui/$UID/$PLIST_ID"
print "立即手动跑一次: $ROOT/scripts/run_xhs_daily_local.sh"
