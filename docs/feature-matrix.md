# Feature Matrix — README Claim vs Actual Code State

> 生成时间：2026-04-20
> 基准：README.md 功能声明 vs 源码实际状态

## 判定标准
- **Complete** — 有独立模块，被主流程调用，可端到端运行
- **Partial** — 有代码骨架但缺关键路径、测试或集成
- **Stub** — 仅类定义/空方法，未实际集成
- **Missing** — README 声明但代码中不存在或已废弃

---

## Email

| 功能 | README 声明 | 实际状态 | 模块 | 说明 |
|------|------------|---------|------|------|
| IMAP 收信 | Multi-protocol — IMAP | **Complete** | `core/imap_client.py` | 256 行，有 real IMAP，支持 async fallback |
| POP3 收信 | Multi-protocol — POP3 | **Partial** | `core/pop3_client.py` | 260 行，有 `sync_emails`/`fetch_message`，但仅在 `connection_tester` 中被引用，sync_worker 未真正调用 |
| Exchange ActiveSync | Multi-protocol — Exchange ActiveSync | **Stub** | `core/activesync_client.py` | 300 行，但 `mail_sync.py:372` 使用 `MockActiveSyncClient`，实际 connect/Sync 未对接真实 EAS |
| Google OAuth2 | OAuth2 (Google / Microsoft) | **Complete** | `core/oauth2_new.py` + `models/account.py` | Google loopback redirect 已实现，token 缓存持久化 |
| Microsoft OAuth2 | OAuth2 (Google / Microsoft) | **Complete** | `core/oauth2_new.py` | Microsoft Device Code 流程已实现 |
| Provider presets | One-click setup for Gmail, Outlook, Yahoo, 163, QQ | **Complete** | `models/account.py:29` | 6 个 provider 预设 |
| Connection testing | Real-time validation, 10 categories | **Complete** | `core/connection_tester.py` | 多协议连接测试，错误分类 |
| Offline queue | Compose/manage offline, auto-send | **Complete** | `core/operation_queue.py` + `queue/` | 操作队列 + 网络监控联动 |
| Draft auto-save | Local autosave + IMAP APPEND sync | **Complete** | `core/draft_autosave.py` + `core/draft_syncer.py` | 本地自动保存 + `\\Drafts` 同步 |
| Attachment management | Add, preview, manage | **Complete** | `ui/mail/attachment_manager.py` + `attachment_preview.py` | 附件管理 + 预览 |
| Email threading | THREAD=REFERENCES + local fallback | **Complete** | `core/thread_builder.py` | 本地 fallback 已实现 |
| Enhanced search (FTS5) | FTS5 + advanced filters, snippets | **Complete** | `storage/search_enhanced.py` | `from:/to:/subject:/has:/is:/after:/before:/in:` 过滤器，snippet 高亮 |
| Semantic search | Sentence Transformers + Faiss | **Complete** | `search/semantic_search.py` + `storage/search_enhanced.py` | 有独立模块 + hybrid_search，优雅降级到 FTS5 |
| Spam filtering | Bayesian + Chinese jieba | **Complete** | `filter/bayes_filter.py` + `filter/tokenizer.py` | unsure 中间态 + 纠错回流 |
| Mail sync | Background sync, per-account status | **Complete** | `core/mail_sync.py` | 可配置间隔，多账户并行 |
| Rich text editor | Formatting toolbar | **Complete** | `ui/mail/compose_window.py` | 工具栏已集成 |
| Filter rules | AND/OR logic, import/export | **Complete** | `filter/enhanced_filter_engine.py` + UI | 多条件类型、优先级 |

## PIM

| 功能 | README 声明 | 实际状态 | 模块 | 说明 |
|------|------------|---------|------|------|
| Calendar | Month/week/day views, CalDAV sync | **Complete** | `ui/calendar/calendar_page.py` + `core/caldav_client.py` | 362 行 CalDAV 实现（httpx），日历 UI 完整 |
| Contacts | Full contact manager | **Complete** | `ui/contacts/` (4 个文件) | 列表/详情/编辑/管理完整 |
| Todos | Priority-based, views | **Complete** | `ui/todo/todo_page.py` | 今天/本周/全部 + 逾期检测 |
| Projects | Kanban-style boards | **Complete** | `ui/project/project_page.py` | 739 行，卡片/列/拖拽重排 |
| Labels | Color-coded labeling | **Complete** | `ui/labels/` | 管理器 + 选择器组件 |
| Calendar reminders | D-Bus desktop reminders | **Complete** | `utils/calendar_reminder.py` | D-Bus 通知集成 |

## UI & Theming

| 功能 | README 声明 | 实际状态 | 模块 | 说明 |
|------|------------|---------|------|------|
| Dark/Light themes | Catppuccin palettes | **Complete** | `ui/resources/styles/` | dark.qss + light.qss |
| Sidebar navigation | Icons + compose button | **Complete** | `ui/sidebar.py` | |
| Toolbar | Sync, compose, add-account | **Complete** | `ui/main_window.py` | |
| Keyboard shortcuts | App-wide + help dialog | **Complete** | `utils/keyboard_shortcuts.py` | |
| Settings page | 5 tabs | **Complete** | `ui/settings/settings_page.py` | 主题/账户/同步/过滤器/通用 |
| Desktop entry | Linux launcher integration | **Complete** | 包含在 `pyproject.toml` 中 | |

## Robustness

| 功能 | README 声明 | 实际状态 | 模块 | 说明 |
|------|------------|---------|------|------|
| Async fallback | Graceful stdlib fallback | **Complete** | `core/imap_client.py` + `core/smtp_client.py` | `try/except` 导入 aioimaplib，降级到 imaplib |
| Crash detection | Detect abnormal exits | **Complete** | `utils/exceptions.py` + `app.py` | 启动时检测 + 日志诊断 |
| Global exception handler | Catch unhandled exceptions | **Complete** | `app.py` | |
| Connection state machine | unverified→verified→sync_ready | **Complete** | `core/connection_status.py` | 6 个状态 |
| Encrypted credentials | cryptography + keyring | **Complete** | `utils/crypto.py` | |
| Account cleanup | Diagnostic tool | **Complete** | `core/account_cleanup.py` + UI | 被 main_window 调用 |
| Background task manager | Daemon thread management | **Complete** | `utils/background_tasks.py` | |

---

## 汇总

| 状态 | 数量 | 功能 |
|------|------|------|
| Complete | 37 | 全部功能 |
| Partial | 1 | POP3 |
| Stub | 1 | Exchange ActiveSync |
| Missing | 0 | 无 |

**结论**: README 功能声明基本准确，两个问题点：
1. POP3 标为 Multi-protocol support 但实际 sync worker 未接入
2. Exchange ActiveSync 标为 Multi-protocol support 但实际仅用 Mock 实现
