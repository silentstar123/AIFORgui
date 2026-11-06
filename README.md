# AIFORgui

面向 AI Agent 的 Windows GUI 操作层，MCP 服务名 `gui-operator-mcp`。

# gui-operator-mcp

给 AI 用的 Windows 桌面操作层：截图、中文 OCR、按文字点击、输入、等文字、摆窗口。通过 **MCP（Model Context Protocol）** 暴露成标准工具，DeepSeek Harness、Claude、Cursor 等客户端都能直接接。

> 不是 RPA，也不是控件自动化。它只负责“看屏幕、动手”，业务判断交给模型和 skill。

## 特点

- **OCR 优先**：按屏幕上的文字点，不依赖控件树/UIA，中文老系统也能用；
- **虚拟屏友好**：枚举物理屏和虚拟屏，坐标用物理像素 + 每屏 DPI；
- **无模型依赖**：服务本身不调用大模型，LLM 由客户端提供；
- **可审计**：每次动作返回命中文字、坐标、第几个匹配，调用方可自行落日志；
- **Windows 优先**：Win10/11，Python 3.10+。

## 工具

| 工具 | 作用 |
|---|---|
| `screen_list` | 列出显示器/虚拟屏、坐标、DPI |
| `screenshot` | 截一块屏，返回 PNG + OCR 文字框 |
| `click_text` | 按文字点击，可指定第几个、是否精确匹配、`dry_run` |
| `click_at` | 按全局物理坐标点击 |
| `type_text` | 经剪贴板输入，支持中文/emoji，可选回车 |
| `press_key` | 组合键，如 `ctrl+l`、`alt+tab` |
| `scroll` | 滚轮 |
| `wait_for_text` | 轮询等文字出现 |
| `window_list` / `window_focus` / `window_place` | 枚举、聚焦、摆窗口 |
| `run_steps` | 批量步骤，逐步留痕，失败即停，可 `expect` 校验 |
| `recycle_paths` | 删除只进回收站；没有永久删除工具 |
| `stop` / `reset_stop` | 停手/恢复；全局热键 **Ctrl+Alt+Q** 也会停 |

### run_steps

```json
{
  "steps": [
    {"action": "click_text", "text": "登录"},
    {"action": "type_text", "text": "demo", "enter": true},
    {"action": "wait_for_text", "text": "首页", "timeout": 10},
    {"action": "screenshot", "screen": 1}
  ],
  "stop_on_error": true,
  "dry_run": false
}
```

每步返回耗时和结果，写入审计日志（默认 `%LOCALAPPDATA%\gui-operator\audit.jsonl`，可用 `GUI_OPERATOR_AUDIT` 覆盖）。`expect` 会在动作后等指定文字出现，没出现就判失败。

## 安装

```powershell
cd plugins\gui-operator
python -m pip install -e .
gui-operator-mcp        # 启动后是 stdio 服务，等客户端发 JSON-RPC
```

依赖：`mss`、`numpy`、`opencv-python`、`rapidocr-onnxruntime`、`pywin32`。

## 接到 DeepSeek Harness

在 profile 的 `cordis.patch.yml` 里加一条 `insert`：

```yaml
- insert:
    - id: mcp-gui-operator
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: gui
        transport: stdio
        command: gui-operator-mcp
        args: []
```

重启后模型会看到 `mcp__gui__screenshot`、`mcp__gui__click_text` 等工具。

也可以不装包，直接：

```yaml
    command: python
    args: ['-m', 'gui_operator_mcp']
    env:
      PYTHONPATH: 'D:\path\to\plugins\gui-operator\src'
```

## 最小示例

模型侧（或手工用 MCP 客户端）：

1. `screen_list` → 看有几块屏；
2. `screenshot {"screen":1}` → 拿到图和 OCR 文字框；
3. `click_text {"text":"开始"}` → 点“开始”；
4. `type_text {"text":"你好","enter":true}`。

`click_text` 的返回：

```json
{"text": "开始", "screen": 1, "x": 960, "y": 540, "matches": 1, "nth": 0, "clicked": true}
```

## 放权限（可选，谨慎）

```powershell
gui-operator-allow-all --profile desktop          # 只显示将写入的内容
gui-operator-allow-all --profile desktop --apply  # 写入（带时间戳备份）
gui-operator-allow-all --profile desktop --revert # 撤销
```

它只改两处：`sandbox-policy.mode = danger-full-access`、`approval.policy = never`，改完要重启 DSH。更推荐在会话里直接用内置命令 `/permission danger-full-access`。放权后模型可以不经确认执行任何桌面/文件操作，只在你完全信任的机器上用。

## 安全边界

- **删除只进回收站**：`recycle_paths` 走 `SHFileOperationW` + `FOF_ALLOWUNDO`；`press_key` 拒绝 `Shift+Delete`；
- **发布前留证**：点击「发布 / 发送 / 提交」前自动截一张图，存 `%LOCALAPPDATA%\gui-operator\evidence`，结果里返回 `evidence` 路径；
- **审计保留 30 天**：`run_steps` 每步写 JSONL，服务启动时自动清理 30 天前的条目（`GUI_OPERATOR_AUDIT_DAYS` 可改）；
- **一键停手**：全局热键 **Ctrl+Alt+Q**，或调用 `stop`；`reset_stop` 恢复；
- 默认**不内置审批**：`click_text` 有 `dry_run`，真正的“发布/删除前停下”由客户端或 skill 负责；
- 不内置验证码识别、风控绕过、自动发帖；
- 点击前核对 OCR 命中文字，点完建议再截图确认；
- UAC/安全桌面无法操作时会报错，不假装成功。

## 已知限制

- Windows 10/11；Linux/macOS 未实现；
- 高 DPI 已处理，但混合缩放的多屏仍建议每屏单独截图；
- OCR 对极小字号、强反光、动态视频效果一般；
- 没有模板匹配/区域 OCR（下一版）。

## 开发

```powershell
python -m pip install -e .[dev]
python -m pytest -q
```

## License

MIT
