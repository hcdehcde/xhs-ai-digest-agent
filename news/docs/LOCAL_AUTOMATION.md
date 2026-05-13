# XHS 本机自动化

当前 Codex 自动化运行环境没有可用外网 DNS，因此真正稳定的“每天自动跑日报”需要放到你的 Mac 本机上执行。

## 安装

默认每天 `22:00` 执行：

```bash
cd /Users/didi/Documents/Codex/2026-04-22-new-chat
./scripts/install_xhs_launchd.sh
```

自定义时间，例如每天 `20:30`：

```bash
cd /Users/didi/Documents/Codex/2026-04-22-new-chat
./scripts/install_xhs_launchd.sh 20 30
```

## 手动跑一次

```bash
cd /Users/didi/Documents/Codex/2026-04-22-new-chat
./scripts/run_xhs_daily_local.sh
```

## 卸载

```bash
cd /Users/didi/Documents/Codex/2026-04-22-new-chat
./scripts/uninstall_xhs_launchd.sh
```

## 输出位置

- 日报 Markdown: `/Users/didi/Documents/Codex/2026-04-22-new-chat/reports/{date}.md`
- 日报 JSON: `/Users/didi/Documents/Codex/2026-04-22-new-chat/reports/{date}.json`
- 每日日志: `/Users/didi/Documents/Codex/2026-04-22-new-chat/reports/logs/daily-{date}.log`
- launchd 标准输出: `/Users/didi/Documents/Codex/2026-04-22-new-chat/reports/launchd.stdout.log`
- launchd 标准错误: `/Users/didi/Documents/Codex/2026-04-22-new-chat/reports/launchd.stderr.log`

## 说明

- 本机网络正常时，脚本会先检查小红书登录态，再生成日报。
- 如果检测到 `network_error`，任务会在 30 秒后自动重试一次；仍失败时会停止并在日志里保留原因。
- 如果未来要附带飞书发送，可以在运行前设置环境变量 `XHS_SEND_FEISHU=1`。
- 当前 launchd 模板已默认开启飞书发送。
