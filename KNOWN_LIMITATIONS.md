# Known Limitations — OpenEmail v0.5.0

## 协议层

### POP3 后台同步未启用
**影响**: POP3 账户可配置、可连接测试，但后台同步线程 (`mail_sync.py`) 不会主动拉取 POP3 邮件。
**原因**: POP3 同步逻辑与 IMAP 差异较大（无文件夹概念、无 IDLE 推送），当前未适配。
**Workaround**: 使用 IMAP 协议替代。

### Exchange ActiveSync 仅 Mock
**影响**: 添加 EAS 账户后，连接测试通过但不会真正同步邮件。
**原因**: `activesync_client.py` 的 `connect()` 使用 `MockActiveSyncClient`（见 `mail_sync.py:372`），真实 EAS XML 协议握手、Sync 命令、WBXML 编解码均未实现。
**Roadmap**: P4 阶段评估 ActiveSync vs Graph API。

### OAuth2 仅支持 Google 和 Microsoft
**影响**: 其他邮箱（如 Yahoo、163）即使支持 OAuth2，当前也只能通过密码认证。
**原因**: `oauth2_new.py` 硬编码了 Google 和 Microsoft 两个 provider。

## 测试覆盖

- 当前仅 5 个测试文件、46 个测试用例
- 无 UI 集成测试 (pytest-qt)
- 核心模块（IMAP/SMTP/Compose/Models/Filters）测试覆盖率低
- 无 CI/CD pipeline
- 目标: v0.6.0 达到 80%+

## 日志体系

- 部分模块仍使用 `print` 输出而非 `logging`
- 空 `except` 块可能导致异常被静默吞掉
- 日志未分级（DEBUG/INFO/WARN/ERROR 不统一）
- 目标: v0.6.0 统一

## 跨平台

- 仅支持 Linux (X11 / Wayland)
- macOS / Windows 适配未开始
- 目标: v1.0.0

## 数据库

- Schema 迁移为单向，不支持回滚
- 崩溃恢复仅检测异常退出，不自动修复损坏数据
- 目标: v0.6.0 完善

## 安全

- 部分模块可能将敏感信息写入日志（待审计）
- S/MIME 和 PGP 未实现
- 目标: PGP/S-MIME 在 v0.9.0

## UI 字符串

- 中英文混杂，硬编码字符串未 externalize
- 无 i18n 流程
- 目标: v0.8.0 完整 i18n

## 插件系统

- 未设计 hook 点和扩展机制
- 目标: v0.9.5 初步设计
