#!/bin/zsh
set -euo pipefail

PLIST_ID="com.codex.xhs-digest"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_ID.plist"

launchctl bootout "gui/$UID/$PLIST_ID" >/dev/null 2>&1 || true

if [[ -f "$TARGET_PLIST" ]]; then
  rm -f "$TARGET_PLIST"
  print "已删除: $TARGET_PLIST"
else
  print "未发现已安装的 plist: $TARGET_PLIST"
fi
