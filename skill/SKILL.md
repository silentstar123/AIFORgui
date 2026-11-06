---
name: gui-operator-mcp
description: 用 gui-operator MCP 工具操作 Windows 桌面：截图、OCR、按文字点击、输入、等文字、摆窗口。需要点一个没有接口的程序或网页时使用。
whenToUse: 用户要求操作 Windows 界面、点按钮、填表单、在桌面程序里做事，且已接入 mcp__gui__* 工具。
---

# 用 MCP 操作 Windows 桌面

工具名以客户端注册为准，DeepSeek Harness 里通常是 `mcp__gui__<tool>`。

## 先看再动

1. `screen_list` 确认屏和坐标；
2. `screenshot`（可 `with_ocr: true`）拿到图 + 文字框；
3. 用 `click_text` 点文字，返回里核对命中文字和坐标；
4. 输入用 `type_text`；快捷键用 `press_key`；
5. 动作后重新 `screenshot` 复核，别假设成功。

## 规矩

- 发布、删除、提交、付款这类动作，先 `dry_run: true` 或截图给用户确认；
- 文字对不上就重新截图，不要凭坐标猜；
- 一次只做一个动作，做完复核；
- 遇到 UAC、锁屏、安全桌面直接停下报告，不要重试；
- 不碰验证码、密码、风控。
