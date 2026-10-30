# 参与贡献

感谢你对快传的关注！提交前请阅读以下约定。

## 提交 Issue

- **Bug**：说明系统版本、快传版本、复现步骤、期望结果与实际结果，附截图更佳。
- **功能建议**：说明使用场景和期望效果。

## 提交 Pull Request

1. Fork 本仓库，从 `main` 创建分支：`feat/拖拽发送`、`fix/搜索超时` 等。
2. 安装开发依赖：`pip install -r requirements-dev.txt`。
3. 修改代码并补充测试，确保 `python -m pytest` 全部通过。
4. 涉及界面改动时，运行 `python scripts/screenshots.py` 更新截图。
5. 在 `CHANGELOG.md` 的未发布版本下记录变更。
6. 提交信息使用 [约定式提交](https://www.conventionalcommits.org/zh-hans/)，如 `feat: 支持拖拽文件发送`、`fix: 修复搜索结果包含本机`。

## 代码规范

- 遵循 PEP 8，单行不超过 120 字符。
- 注释与文档使用中文，说明「为什么这么做」，而不只是「做了什么」。
- 后台线程不直接操作界面，只通过事件队列通知界面线程（见 `transfer.py` 模块说明）。
- 界面颜色、字号只从 `ui/theme.py` 取，不在页面中硬编码。
- 修改通信协议时同步更新 `docs/protocol.md`，并保持向下兼容或升级 `DISCOVER_MAGIC`。
