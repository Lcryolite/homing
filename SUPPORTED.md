# Supported Features — OpenEmail v0.5.0

> 本文件列出当前版本经过验证的功能，不包含 roadmap 中规划但尚未实现的特性。

## 邮件协议

| 协议 | 状态 | 说明 |
|------|------|------|
| IMAP | ✅ 支持 | 收信、文件夹管理、IDLE 推送（代码已集成，依赖服务端 capability） |
| SMTP | ✅ 支持 | 发信（同步 + 异步 fallback） |
| POP3 | ⚠️ 部分支持 | 代码有 fetch_message/sync_emails，但后台同步未调用，仅供连接测试 |
| Exchange ActiveSync | ❌ 仅骨架 | Mock 实现，未对接真实 EAS 服务器 |
| CalDAV | ✅ 支持 | 日历列表发现、VEVENT/VTODO 读写、增量同步 |

## 认证方式

| 方式 | 状态 | 说明 |
|------|------|------|
| Plain password | ✅ 支持 | IMAP/SMTP |
| App-specific password | ✅ 支持 | Gmail 等需要应用专用密码的场景 |
| Google OAuth2 | ✅ 支持 | Loopback redirect，token 缓存持久化，自动刷新 |
| Microsoft OAuth2 | ✅ 支持 | Device code flow |

## 邮箱 Provider 预设

Gmail, Outlook, Yahoo, 163, QQ — 支持预设参数自动填充

## 搜索

| 功能 | 状态 |
|------|------|
| FTS5 全文搜索 | ✅ |
| 高级过滤器 (from:, to:, subject:, has:, is:, after:, before:, in:) | ✅ |
| Snippet 摘要高亮 | ✅ |
| 语义搜索 (Sentence Transformers + Faiss) | ✅ — 优雅降级到 FTS5 |
| 搜索历史与建议 | ✅ |

## 垃圾过滤

| 功能 | 状态 |
|------|------|
| 贝叶斯分类器 | ✅ |
| 中文分词 (jieba) | ✅ |
| unsure 中间态 | ✅ |
| 纠错回流训练 | ✅ |

## PIM 模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 日历 | ✅ | 月/周/日视图、颜色编码、CalDAV 同步、D-Bus 提醒 |
| 联系人 | ✅ | 列表/详情/编辑 |
| 待办事项 | ✅ | 优先级、今天/本周/全部视图、逾期检测 |
| 项目看板 | ✅ | Kanban 风格、卡片/列、拖拽重排 |
| 标签 | ✅ | 颜色编码、选择器 |

## UI

| 功能 | 状态 |
|------|------|
| Dark / Light 主题 (Catppuccin) | ✅ |
| 侧边栏导航 | ✅ |
| 工具栏 | ✅ |
| 快捷键系统 + 帮助对话框 | ✅ |
| 设置页面 (5 标签页) | ✅ |

## 鲁棒性

| 功能 | 状态 |
|------|------|
| Async→stdlib 优雅降级 | ✅ |
| 崩溃检测与恢复 | ✅ |
| 全局异常捕获 | ✅ |
| 连接状态机 (6 状态) | ✅ |
| 加密凭据存储 (cryptography + keyring) | ✅ |
| 账户诊断清理工具 | ✅ |
| 后台任务管理器 | ✅ |
| 网络状态监控 | ✅ |
| 离线操作队列 | ✅ |

## 系统要求

- Python >= 3.11
- PyQt6 >= 6.11
- Linux (X11 / Wayland)
