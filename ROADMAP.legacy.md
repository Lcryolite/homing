# OpenEmail Development Roadmap

> 核心原则：按闭环推进，不按功能清单累加。每个闭环完成 = 用户可感知的质变。
> 每完成一个闭环，进行 git commit 并推送到远程仓库。

---

## 闭环一：稳定性与安全闭环（P0）

**完成标准**：应用可稳定启动，无 ImportError；所有数据库写操作走参数化；核心模块有测试覆盖。

**完成后动作**：git commit + push，tag: `v0.2.0`

| # | 任务 | 完成标准 |
|---|------|----------|
| 1 | 补齐缺失模块 | `network_monitor.py`、`operation_queue.py`、`account_cleanup.py`、`validation_snapshot.py` 实现或移除引用 |
| 2 | 修复代码缺陷 | 重复方法、不存在的属性引用、双重装饰器、重复 except 等全部修复 |
| 3 | 安全修复 | `email_operations.py`、`offline_queue.py` 迁移到参数化/安全 API |
| 4 | 系统文件夹发现升级 | `Folder.get_system_folders()` → RFC 6154 SPECIAL-USE 发现 + 本地回退，为草稿/已发送/垃圾箱打地基 |
| 5 | 测试基础设施 | 启动 smoke test + 核心模型/协议/过滤器测试（pytest + pytest-qt），作为发布闸门 |

---

## 闭环二：核心邮件闭环（P1）

**完成标准**：真实用户可把 OpenEmail 当主力收发客户端使用一周。

**完成后动作**：git commit + push，tag: `v0.3.0`

| # | 任务 | 完成标准 | 关键技术点 |
|---|------|----------|------------|
| 6 | 草稿自动保存 | 本地 autosave + 远端 \Drafts 同步（IMAP APPEND）；APPENDUID 映射；继续编辑草稿 | RFC 6154 + APPEND |
| 7 | IMAP IDLE + 连接生命周期管理 | IDLE capability 检查 → 29 分钟重置 → 断线重入 → 失败回退 NOOP/轮询；与网络监控/自动重连/离线队列合并为一个 Epic | RFC 2177，Python >=3.14 可用 `imaplib.IMAP4.idle()` |
| 8 | Microsoft OAuth2 | public-client 交互式授权；token cache 持久化；IMAP/SMTP OAuth scope 接入 | Microsoft 文档已明确支持 IMAP/SMTP via OAuth |
| 9 | 新邮件桌面通知 | IDLE 推送 -> D-Bus 通知；与 IDLE 打通后用户感知极强 | freedesktop.org 通知规范 |
| 10 | UI 字符串整理 | 中英混杂统一、硬编码字符串 externalize，为后续 i18n 打基础 | Qt tr() 机制 |

---

## 闭环三：组织与检索闭环（P2）

**完成标准**：邮件不只是"能收发"，还能高效组织和找回。

**完成后动作**：git commit + push，tag: `v0.4.0`

| # | 任务 | 完成标准 | 关键技术点 |
|---|------|----------|------------|
| 11 | 线程/会话视图 | 优先检测 THREAD=REFERENCES 服务端能力；无则本地 fallback | RFC 5256 |
| 12 | 贝叶斯垃圾过滤完整流水线 | 训练 -> 分类 -> unsure 中间态 -> 纠错回流 -> 标注 UI | 依赖闭环一/二的稳定消息模型和测试 |
| 13 | FTS5 搜索做实 | 关键词搜索、snippet 摘要、highlight 高亮、性能优化 | 先不碰 embeddings |
| 14 | CalDAV 基础同步 | 日历列表拉取、VEVENT/VTODO 读写、最近变更同步；暂不做调度邀请 | RFC 4791，调度留到 RFC 6638 |

---

## P3：体验增强

**完成后动作**：git commit + push，tag: `v0.5.0`

| # | 任务 | 备注 |
|---|------|------|
| 15 | 富文本编辑器 | 从"安全且有限的样式子集"开始，不追求全功能网页编辑器 |
| 16 | 快捷键系统 | Qt QShortcut，低风险高回报 |
| 17 | 日历提醒通知 | 与 D-Bus 通知复用 |
| 18 | 语义搜索重排 | FTS5 做实之后，再加 Sentence Transformers + Faiss |
| 19 | 账户清理工具 | |

---

## P4：长线战略

**完成后动作**：git commit + push，tag: `v1.0.0`

| # | 任务 | 备注 |
|---|------|------|
| 20 | ActiveSync 路线评估 | 改为评估项，非直接实现；评估 Graph API vs ActiveSync vs 继续走 IMAP/SMTP+CalDAV |
| 21 | PGP/S-MIME | 等核心数据模型和 MIME 生成稳定后再推进 |
| 22 | 插件系统 | 先内部 hook/extension seam 验证扩展点，稳定后再做正式 SDK |
| 23 | 完整 i18n | Qt Linguist 流程，闭环二已做字符串 externalize 打底 |
| 24 | 多平台适配 | macOS / Windows |

---

## 版本里程碑

| 版本 | 对应闭环 | 目标 |
|------|----------|------|
| v0.2.0 | 闭环一 | 稳定可启动、安全、有测试 |
| v0.3.0 | 闭环二 | 可当主力收发客户端日用一周 |
| v0.4.0 | 闭环三 | 邮件组织与检索能力完整 |
| v0.5.0 | P3 | 体验提升 |
| v1.0.0 | P4 | 首个正式发布 |

---

## 纪律

1. 每个闭环内所有任务全部完成后，才算闭环闭合
2. 闭环闭合后必须 git commit + push + tag
3. 不跳闭环，不跨闭环合并 commit
4. 闭环内任务可并行，但闭环之间严格串行
