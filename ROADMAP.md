# OpenEmail 可执行 Roadmap（AI 执行版）

版本范围：**v0.5.0 → v1.0.0**  
编制日期：**2026-04-20**  
适用对象：**AI 编码代理 / 项目维护者 / 技术负责人**

---

## 1. 这份 roadmap 的目标

这份 roadmap 不是“功能愿望清单”，而是**可以直接交给 AI 按阶段执行**的工程计划。核心原则只有一句话：

> **在 v1.0.0 之前，优先把 OpenEmail 做成一个稳定、可托付、可恢复、可发布的 Linux 桌面邮件客户端；不要继续扩张大功能面。**

也就是说，v1.0 的重点不是插件、不是跨平台、也不是一口气把所有 PIM 模块都做到很深，而是：

- 账号配置可用
- OAuth2 可用
- 收信、发信、草稿、已发送、搜索、附件、线程视图可用
- 崩溃后可恢复
- 本地数据和日志可控
- Linux 包可安装
- 文档状态与代码真实状态一致

---

## 2. v1.0 的产品边界（必须先定死）

### 2.1 v1.0 的正式目标

OpenEmail v1.0.0 定义为：

> **Linux-first、本地优先、支持主流 IMAP/SMTP 和 OAuth2 的原生桌面邮件客户端，附带基础可用的日历与联系人模块。**

### 2.2 v1.0 必须稳定的功能

以下能力必须进入 **Stable**：

1. 多账户管理
2. IMAP 收信
3. SMTP 发信
4. Gmail OAuth2 登录与发信
5. Outlook OAuth2 登录与发信
6. Generic IMAP/SMTP（密码 / app password）
7. 文件夹发现与 SPECIAL-USE 映射
8. 草稿本地自动保存
9. Drafts 远端同步
10. Sent folder 保存
11. 附件添加、保存、基本预览
12. 线程视图
13. FTS5 搜索
14. 离线队列与重连恢复
15. 崩溃恢复与诊断日志
16. Linux 安装分发（至少 AppImage / Flatpak 之一稳定，最好两者都有）

### 2.3 v1.0 可以保留为 Beta 的功能

以下能力可以进入 **Beta**，但不能阻塞 v1.0：

1. CalDAV 日历同步
2. 联系人管理
3. Bayesian 垃圾过滤
4. 语义搜索（必须默认关闭，手动开启）
5. TODO 模块
6. Projects 模块

### 2.4 v1.0 前不应该投入主力的功能

以下能力应标为 **Experimental / Deferred**，不进入 v1.0 主路径：

1. ActiveSync 的完整产品化
2. Graph API 大迁移
3. PGP / S/MIME
4. 插件系统
5. Windows / macOS 正式支持
6. 默认启用语义搜索
7. 深度项目管理能力
8. 复杂自动化工作流系统

---

## 3. AI 执行总规则

这部分是给 AI 的硬约束，建议直接照抄执行。

### 3.1 Phase 严格串行

- 不允许跨 Phase 抢跑
- 一个 Phase 未完成前，不进入下一个 Phase
- 一个任务未完成前，不做“顺手加功能”

### 3.2 一次只完成一个任务

每次只执行一个任务卡（例如 `T0.1`）。完成后必须输出：

1. 修改的文件列表
2. 做了什么改动
3. 运行了哪些验证命令
4. 是否通过
5. 残余风险
6. 下一步建议

### 3.3 每个任务必须满足最小交付要求

每个任务至少包含：

- 代码改动
- 测试或 smoke 验证
- 文档同步更新
- 无新增 `print(`
- 无 bare `except:`
- 不引入新的未解释 TODO

### 3.4 不允许夸大 README

README、功能列表、版本说明必须与代码真实状态一致：

- 已稳定：可写 Stable
- 代码存在但未闭环：只能写 Beta
- 仅有雏形或未验证：写 Experimental
- 还没做：写 Planned

### 3.5 安全与隐私规则

- token、密码、授权头、cookie、邮件正文不得写入普通日志
- 崩溃报告必须可脱敏
- HTML 邮件默认阻止外部内容
- 草稿、队列、迁移、附件处理要考虑异常中断恢复

### 3.6 完成定义（Definition of Done）

一个任务完成，至少满足：

- 代码已提交
- 测试或 smoke 通过
- 文档已更新
- 没有明显回归
- 当前任务的验收条件全部满足

---

## 4. 发布里程碑总览

| 版本 | 目标 | 核心主题 |
|---|---|---|
| v0.6.0 | 事实对齐 + 质量地基 | 文档、版本、CI、日志、迁移、安全基线 |
| v0.7.0 | 核心收发链路稳定 | 账号、OAuth2、IMAP/SMTP、Drafts、Queue |
| v0.8.0 | Linux Beta | 搜索、存储、性能、PIM 收口、打包 |
| v0.9.0 | 安全与恢复强化 | HTML 安全、日志脱敏、恢复工具、诊断 |
| v1.0.0 | 正式发布 | 文档、回归、安装包、Beta 修复、发布材料 |

---

# Phase 0 — v0.6.0：事实对齐 + 质量地基

**目标：** 先把项目“说的”和“做的”对齐，再把基础工程能力搭起来。  
**原则：** 本阶段不新增大型功能，只做对齐、清理、加固。

---

## T0.1 功能状态审计与文档对齐

**优先级：P0**

### 目标
建立单一事实来源，避免 README、roadmap、代码状态互相打架。

### 涉及文件
- `README.md`
- `ROADMAP.md`
- `docs/feature-matrix.md`（新建）
- `SUPPORTED.md`（新建）
- `KNOWN_LIMITATIONS.md`（新建）

### 执行内容
1. 全面盘点 README 中所有功能声明。
2. 将每项功能标记为：`Stable / Beta / Experimental / Planned`。
3. 新建 `docs/feature-matrix.md`，按模块列出：
   - 功能名
   - 后端状态
   - UI 状态
   - 测试状态
   - 支持范围
   - 对外标签
4. 新建 `SUPPORTED.md`，明确区分：
   - Gmail
   - Outlook
   - Generic IMAP/SMTP
   - POP3
   - ActiveSync
5. 新建 `KNOWN_LIMITATIONS.md`，把当前已知边界写清楚。
6. 修改 README 中夸大或未闭环的表述。

### 产出物
- `docs/feature-matrix.md`
- `SUPPORTED.md`
- `KNOWN_LIMITATIONS.md`
- 修订后的 `README.md`

### 验收标准
- README 中不再出现明显与当前代码状态冲突的描述
- 所有高风险功能都有状态标记
- 用户能看懂什么是稳定、什么是实验性

### 验证命令
```bash
grep -n "Experimental\|Beta\|Stable\|Planned" README.md SUPPORTED.md KNOWN_LIMITATIONS.md docs/feature-matrix.md
```

### 推荐提交信息
```bash
git commit -m "phase0: align feature claims and support matrix"
```

---

## T0.2 版本号与依赖定义对齐

**优先级：P0**

### 目标
清理版本号混乱和依赖定义混乱的问题。

### 涉及文件
- `pyproject.toml`
- `src/openemail/__init__.py`
- `README.md`
- `CHANGELOG.md`（新建）

### 执行内容
1. 将 `pyproject.toml` 的版本号提升到当前开发目标版本（建议先改为 `0.6.0`）。
2. 在 `src/openemail/__init__.py` 中添加 `__version__`。
3. 新建 `CHANGELOG.md`，至少整理出当前版本之前的重要变更摘要。
4. 在 `pyproject.toml` 中按 extras 划分依赖：
   - `dev`
   - `oauth`
   - `semantic`
   - `spam`
5. 让 README 安装命令与真实依赖安装方式一致。

### 产出物
- 统一版本号
- 依赖 extras
- `CHANGELOG.md`

### 验收标准
- `import openemail; print(openemail.__version__)` 可用
- 安装说明与依赖表述一致
- 语义搜索等可选功能不再伪装成基础依赖

### 验证命令
```bash
python -c "import openemail; print(openemail.__version__)"
python -m pip install -e .
```

### 推荐提交信息
```bash
git commit -m "phase0: align versioning and dependency extras"
```

---

## T0.3 建立最小可用 CI

**优先级：P0**

### 目标
让每次提交都能自动做基础检查。

### 涉及文件
- `.github/workflows/ci.yml`（新建）
- `pyproject.toml`
- `README.md`

### 执行内容
1. 新建 GitHub Actions CI。
2. 至少包含以下 job：
   - `ruff check .`
   - `pytest tests/ -q`
   - `python -m pip install -e .`
   - `python -c "import openemail"`
3. 如 mypy 现阶段噪音太大，可先以宽松模式启用，或留到 Phase 1 后段。
4. README 中补充“本地开发前请先跑这些命令”。

### 产出物
- 最小 CI 流程

### 验收标准
- push / PR 自动触发
- 至少有 lint、test、install、import 四项检查

### 验证命令
```bash
ruff check .
pytest tests/ -q
python -m pip install -e .
python -c "import openemail"
```

### 推荐提交信息
```bash
git commit -m "phase0: add baseline CI workflow"
```

---

## T0.4 日志统一与敏感信息脱敏

**优先级：P0**

### 目标
把 `print`、裸异常、敏感日志问题先解决掉。

### 涉及文件
- `src/openemail/main.py`
- `src/openemail/app.py`
- `src/openemail/utils/`
- `src/openemail/core/`
- `src/openemail/ui/`

### 执行内容
1. 全局搜索 `print(` 并逐步替换成标准 `logging`。
2. 配置统一 logger 初始化入口。
3. 增加日志脱敏过滤器，至少遮蔽：
   - token
   - password
   - Authorization header
   - Cookie
   - refresh token
4. 修复 bare `except:`，改为具体异常并记录合理级别日志。
5. 将 file log 写入 `~/.openemail/openemail.log`，并加轮转策略。

### 产出物
- 统一日志系统
- 敏感信息脱敏机制

### 验收标准
- `grep -R "print(" src/openemail` 结果为 0
- `grep -R "except:" src/openemail` 结果为 0 或仅极少数有充分注释的特殊场景
- debug 日志不直接泄露凭据

### 验证命令
```bash
grep -R "print(" src/openemail || true
grep -R "except:" src/openemail || true
python -m openemail.main --debug
```

### 推荐提交信息
```bash
git commit -m "phase0: standardize logging and redact secrets"
```

---

## T0.5 测试地基：统一 fixture、临时 DB、样例邮件

**优先级：P0**

### 目标
给后续协议测试、存储测试、搜索测试搭好地基，避免每个测试各写一套环境。

### 涉及文件
- `tests/conftest.py`
- `tests/fixtures/`（新建）
- `tests/helpers/`（新建，可选）

### 执行内容
1. 在 `tests/conftest.py` 中建立统一的：
   - 临时配置目录
   - 临时数据库
   - 临时附件目录
   - 测试账户工厂
2. 新建样例邮件 fixture：
   - 纯文本
   - HTML
   - multipart/alternative
   - inline image
   - attachment
   - reply/forward 头信息
3. 建立测试用 settings / account / folder 工厂函数。

### 产出物
- 可复用测试环境
- 邮件 fixture 集

### 验收标准
- 后续测试文件无需重复造环境
- mail builder/parser 测试可直接复用 fixture

### 验证命令
```bash
pytest tests/ -q
```

### 推荐提交信息
```bash
git commit -m "phase0: add shared test fixtures and mail samples"
```

---

## T0.6 数据库迁移加固

**优先级：P0**

### 目标
让迁移失败时可回滚、不破坏现有库。

### 涉及文件
- `src/openemail/storage/database.py`
- `src/openemail/storage/migrations.py`
- `tests/test_database.py`
- `tests/test_migrations.py`

### 执行内容
1. 审查所有 migration step，避免重复 `ALTER`、重名表、不可重复执行逻辑。
2. 给迁移过程加事务和 rollback。
3. 保证 `schema_version` 正确递增。
4. 新增以下测试：
   - 空库初始化
   - 旧版本升级
   - 重复执行迁移
   - 故意失败迁移时回滚

### 产出物
- 更安全的 migration 流程
- 迁移测试

### 验收标准
- 升级失败不会留下半迁移状态
- 重复执行不会炸库

### 验证命令
```bash
pytest tests/test_database.py tests/test_migrations.py -q
```

### 推荐提交信息
```bash
git commit -m "phase0: harden database migrations and rollback"
```

---

## T0.7 崩溃恢复基础能力

**优先级：P1**

### 目标
让应用异常退出后，有清晰恢复路径，而不是让用户自己猜。

### 涉及文件
- `src/openemail/app.py`
- `src/openemail/utils/exceptions.py`
- `src/openemail/queue/offline_queue.py`
- `src/openemail/ui/main_window.py`

### 执行内容
1. 启动时检查 crash flag / crash log。
2. 异常退出后，下次启动显示恢复对话框。
3. 离线队列中 `pending / processing` 状态的任务支持重放。
4. 正常退出时清理 crash flag。

### 产出物
- crash recover dialog
- 队列重放能力

### 验收标准
- 异常退出后可见恢复提示
- 队列恢复不重复发送已成功邮件

### 验证命令
```bash
pytest -k "offline_queue or crash or recovery" -q
```

### 推荐提交信息
```bash
git commit -m "phase0: add crash recovery and queue replay groundwork"
```

---

# Phase 1 — v0.7.0：核心收发链路稳定

**目标：** 让 OpenEmail 真正具备“账号可配、邮件可收、邮件可发、草稿不丢、断网能恢复”的核心能力。  
**原则：** 本阶段只做邮件主链路，不扩功能面。

---

## T1.1 账户模型与 provider preset 收口

**优先级：P0**

### 目标
明确每种 provider 真正支持的协议和认证方式，避免 UI 乱给选项。

### 涉及文件
- `src/openemail/models/account.py`
- `src/openemail/ui/mail/account_dialog.py`
- `src/openemail/core/connection_status.py`
- `tests/test_account.py`

### 执行内容
1. 收口 provider preset 数据结构。
2. 为 Gmail、Outlook、Generic 定义受支持认证方式。
3. 在 UI 中动态展示真正支持的配置项。
4. 明确 POP3、EAS 的实验性标签。
5. 清理占位字段和半实现选项。

### 验收标准
- 账户配置页不再出现“看起来能选、其实不能用”的选项
- preset 行为有测试覆盖

### 验证命令
```bash
pytest tests/test_account.py -q
```

### 推荐提交信息
```bash
git commit -m "phase1: tighten provider presets and account model"
```

---

## T1.2 连接测试器与状态机 UI 闭环

**优先级：P0**

### 目标
连接测试必须从“内部能力”变成“用户能理解的界面行为”。

### 涉及文件
- `src/openemail/core/connection_tester.py`
- `src/openemail/core/connection_status.py`
- `src/openemail/ui/mail/account_dialog.py`
- `tests/test_connection_tester.py`
- `tests/test_connection_status.py`

### 执行内容
1. 在账号配置 UI 中接入“测试连接”按钮。
2. 测试结果显示：
   - verified
   - auth_failed
   - network_failed
   - disabled
3. 将错误类别映射到可读建议。
4. 测试结果写入账户状态模型。
5. 保证 UI 和状态机一致。

### 验收标准
- 用户无需看日志也能知道失败原因与下一步建议
- 状态机与 UI 文案不冲突

### 验证命令
```bash
pytest tests/test_connection_tester.py tests/test_connection_status.py -q
```

### 推荐提交信息
```bash
git commit -m "phase1: integrate connection tester with account UI"
```

---

## T1.3 IMAP/SMTP 认证闭环（密码 / app password / OAuth2）

**优先级：P0**

### 目标
把最关键的三条登录路径真正打通。

### 涉及文件
- `src/openemail/core/imap_client.py`
- `src/openemail/core/smtp_client.py`
- `src/openemail/core/oauth2_new.py`
- `tests/test_imap_client.py`
- `tests/test_smtp_client.py`
- `tests/test_oauth2.py`

### 执行内容
1. 统一认证接口，避免 IMAP 和 SMTP 各写一套分支逻辑。
2. Gmail OAuth2：收信 + 发信闭环。
3. Outlook OAuth2：收信 + 发信闭环。
4. Generic IMAP/SMTP：密码 / app password 路径闭环。
5. token 过期自动刷新。
6. 认证失败时返回明确错误码和 UI 友好提示。

### 验收标准
至少能稳定验证以下三条路径：
1. Gmail OAuth2
2. Outlook OAuth2
3. Generic IMAP/SMTP 密码登录

### 验证命令
```bash
pytest tests/test_imap_client.py tests/test_smtp_client.py tests/test_oauth2.py -q
```

### 推荐提交信息
```bash
git commit -m "phase1: close IMAP and SMTP auth flows"
```

---

## T1.4 首次同步与增量同步正确性

**优先级：P0**

### 目标
保证同步不会漏信、重信、错状态。

### 涉及文件
- `src/openemail/core/mail_sync.py`
- `src/openemail/storage/mail_store.py`
- `src/openemail/models/email.py`
- `tests/test_mail_store.py`
- 新增同步相关测试文件

### 执行内容
1. 明确首次同步策略。
2. 明确增量同步游标策略。
3. 避免重复入库。
4. 补全已读、已标记、删除、移动等状态同步规则。
5. 对失败中断后的恢复进行处理。

### 验收标准
- 中断后重试不会重复堆积相同邮件
- 状态同步逻辑可预期

### 验证命令
```bash
pytest -k "mail_sync or mail_store" -q
```

### 推荐提交信息
```bash
git commit -m "phase1: stabilize initial and incremental mail sync"
```

---

## T1.5 文件夹发现与 SPECIAL-USE 映射

**优先级：P0**

### 目标
让 Sent、Drafts、Trash、Archive 等文件夹行为可预测。

### 涉及文件
- `src/openemail/models/folder.py`
- `src/openemail/core/imap_client.py`
- `tests/test_folder.py`

### 执行内容
1. 建立 SPECIAL-USE 识别逻辑。
2. 建立 provider 差异回退策略。
3. 处理文件夹重命名 / 删除 / 再发现。
4. 明确 Drafts / Sent / Trash 默认映射。

### 验收标准
- Drafts 和 Sent 不依赖用户猜文件夹
- 常见邮箱服务的特殊文件夹可正确识别

### 验证命令
```bash
pytest tests/test_folder.py -q
```

### 推荐提交信息
```bash
git commit -m "phase1: improve folder discovery and special-use mapping"
```

---

## T1.6 发信链路：MailBuilder、附件、Sent copy

**优先级：P0**

### 目标
保证生成的邮件结构正确，附件、引用回复、已发送副本都能工作。

### 涉及文件
- `src/openemail/core/mail_builder.py`
- `src/openemail/core/smtp_client.py`
- `tests/test_mail_builder.py`
- `tests/test_smtp_client.py`

### 执行内容
1. 补全 MailBuilder 测试覆盖。
2. 验证附件 MIME、inline、reply header。
3. 发信成功后写入 Sent folder 或本地已发送记录。
4. 失败时不要误写已发送。

### 验收标准
- 发信成功和失败路径清晰分离
- reply / forward header 正确
- 附件结构正确

### 验证命令
```bash
pytest tests/test_mail_builder.py tests/test_smtp_client.py -q
```

### 推荐提交信息
```bash
git commit -m "phase1: harden outgoing mail builder and sent copy flow"
```

---

## T1.7 草稿自动保存与远端 Drafts 同步

**优先级：P0**

### 目标
草稿不能丢，本地草稿与 IMAP Drafts 必须形成闭环。

### 涉及文件
- `src/openemail/core/draft_autosave.py`
- `src/openemail/core/draft_syncer.py`
- `src/openemail/ui/mail/compose_window.py`
- 新增草稿相关测试

### 执行内容
1. 30 秒自动保存本地草稿。
2. 关闭窗口前强制保存未发送编辑状态。
3. 远端 APPEND 到 `Drafts`。
4. 再次打开时可恢复草稿。
5. 编辑已存在 Drafts 时避免生成大量重复副本。

### 验收标准
- 关闭应用后重新打开，可恢复最近草稿
- 远端 Drafts 能看到对应内容

### 验证命令
```bash
pytest -k "draft or compose_window" -q
```

### 推荐提交信息
```bash
git commit -m "phase1: add local autosave and remote draft sync"
```

---

## T1.8 离线队列幂等、重试与恢复

**优先级：P0**

### 目标
断网后排队、恢复后发送，但绝不能重复乱发。

### 涉及文件
- `src/openemail/queue/offline_queue.py`
- `src/openemail/queue/email_operations.py`
- `tests/test_offline_queue.py`

### 执行内容
1. 给队列任务增加幂等键。
2. 增加指数退避和最大重试次数。
3. 区分可重试错误和不可重试错误。
4. 恢复发送后正确更新状态。
5. 应用崩溃后能重放未完成任务。

### 验收标准
- 网络抖动不会导致同一封邮件重复发送
- 失败重试可控

### 验证命令
```bash
pytest tests/test_offline_queue.py -q
```

### 推荐提交信息
```bash
git commit -m "phase1: add idempotency and retry policy to offline queue"
```

---

## T1.9 线程视图正确性与回退策略

**优先级：P1**

### 目标
在线程信息不足时也能稳定展示，不要因为少量异常邮件把视图打坏。

### 涉及文件
- `src/openemail/core/thread_builder.py`
- `src/openemail/models/email.py`
- 线程相关测试文件

### 执行内容
1. 优先使用 `THREAD=REFERENCES`。
2. 不支持时用本地 fallback。
3. 对缺失 `Message-ID`、损坏 `References` 的邮件做降级处理。
4. 删除 / 移动 / 重同步后，线程可重建。

### 验收标准
- 异常邮件不会拖垮整组会话显示
- 本地回退策略可测试

### 验证命令
```bash
pytest -k "thread" -q
```

### 推荐提交信息
```bash
git commit -m "phase1: harden thread building and fallback behavior"
```

---

# Phase 2 — v0.8.0：搜索、存储、性能、Linux Beta

**目标：** 让大邮箱可用、搜索可信、存储可维护，并交付 Linux Beta。  
**原则：** 本阶段把“本地客户端体验”做顺，不继续堆新协议。

---

## T2.1 FTS5 搜索语法与结果一致性

**优先级：P0**

### 目标
让基础搜索成为用户可信赖的功能。

### 涉及文件
- `src/openemail/storage/search.py`
- `src/openemail/storage/search_enhanced.py`
- `src/openemail/ui/mail/search_bar.py`
- `src/openemail/ui/search/search_enhanced_ui.py`
- 搜索测试文件

### 执行内容
1. 固化支持的搜索语法：
   - `from:`
   - `to:`
   - `subject:`
   - `has:`
   - `is:`
   - `after:`
   - `before:`
   - `in:`
2. 为每种语法增加解析与结果测试。
3. 结果高亮、空结果提示、错误语法提示。
4. 保证本地状态与搜索结果一致。

### 验收标准
- 搜索语法可文档化
- 结果可复现、可解释

### 验证命令
```bash
pytest -k "search" -q
```

### 推荐提交信息
```bash
git commit -m "phase2: stabilize FTS search syntax and result consistency"
```

---

## T2.2 语义搜索降级为实验性并做成可选能力

**优先级：P1**

### 目标
把语义搜索从“默认卖点”改为“实验特性”，避免拖累安装和性能。

### 涉及文件
- `src/openemail/storage/search_enhanced.py`
- `src/openemail/ui/settings/settings_page.py`
- `README.md`
- `docs/feature-matrix.md`

### 执行内容
1. 语义搜索默认关闭。
2. 缺失依赖时自动降级到 FTS5。
3. 设置页增加启用开关与说明。
4. README 改为 Experimental。
5. 加入索引建立进度与取消机制（最小可用版本即可）。

### 验收标准
- 未安装额外依赖时应用照常工作
- 用户清楚知道这是实验性功能

### 验证命令
```bash
pytest -k "semantic or search_enhanced" -q
```

### 推荐提交信息
```bash
git commit -m "phase2: make semantic search opt-in experimental"
```

---

## T2.3 存储模型、附件路径与清理机制

**优先级：P0**

### 目标
明确什么进数据库、什么走文件系统，避免附件和缓存越来越乱。

### 涉及文件
- `src/openemail/storage/mail_store.py`
- `src/openemail/storage/database.py`
- 附件相关 UI/逻辑
- 存储测试文件

### 执行内容
1. 明确附件存储路径策略。
2. 增加 orphan 附件扫描与清理逻辑。
3. 补充文件删除、移动、恢复时的路径一致性处理。
4. 避免数据库记录与磁盘文件脱节。

### 验收标准
- 删除邮件或清理缓存后，附件状态可预测
- 附件路径管理不再是隐式行为

### 验证命令
```bash
pytest tests/test_mail_store.py -q
```

### 推荐提交信息
```bash
git commit -m "phase2: formalize attachment storage and cleanup behavior"
```

---

## T2.4 索引与诊断工具

**优先级：P0**

### 目标
当搜索、FTS、语义索引出问题时，用户和维护者有修复入口。

### 涉及文件
- `src/openemail/ui/tools/`
- `src/openemail/storage/search_enhanced.py`
- `src/openemail/storage/search.py`

### 执行内容
1. 新增“重建 FTS 索引”工具。
2. 新增“重建语义索引”工具（若启用语义搜索）。
3. 新增“存储诊断”或“数据库健康检查”入口。
4. 将这些工具纳入设置或工具页面。

### 验收标准
- 用户无需删库即可尝试自助修复搜索问题

### 验证命令
```bash
pytest -k "search or tool or cleanup" -q
```

### 推荐提交信息
```bash
git commit -m "phase2: add index rebuild and storage diagnostic tools"
```

---

## T2.5 大邮箱性能基线

**优先级：P1**

### 目标
保证邮件量上来后，列表、搜索、启动仍能接受。

### 涉及文件
- `src/openemail/ui/mail/mail_list.py`
- `src/openemail/ui/mail/mail_list_enhanced.py`
- `src/openemail/storage/`
- 可选：性能测试脚本

### 执行内容
1. 建立 10k / 50k 级别的本地测试数据集。
2. 记录启动时间、搜索时间、滚动体验。
3. 对列表做 lazy load / 虚拟化 / 分页优化。
4. 优化大查询和索引命中。

### 验收标准
- 在中大型邮箱上不会出现明显卡死或搜索不可用

### 验证命令
```bash
pytest -q
python -m openemail.main --debug
```

### 推荐提交信息
```bash
git commit -m "phase2: improve list and search performance for large mailboxes"
```

---

## T2.6 Linux 打包与 Beta 分发

**优先级：P0**

### 目标
让外部测试者可以真正安装使用，而不是只会从源码运行。

### 涉及文件
- `packaging/appimage/`
- `packaging/flatpak/`
- `packaging/desktop/openemail.desktop`
- GitHub Actions 发布相关配置

### 执行内容
1. 至少完成一个稳定分发格式（建议 AppImage 先落地）。
2. 如资源允许，再补 Flatpak。
3. 补齐 `.desktop` 文件、图标、启动参数。
4. 生成带 commit hash 的 Beta 包。

### 验收标准
- Linux 用户可以不看源码直接安装试用

### 验证命令
```bash
# 按你的打包脚本执行
bash packaging/appimage/build.sh
```

### 推荐提交信息
```bash
git commit -m "phase2: add Linux packaging for beta distribution"
```

---

# Phase 3 — v0.9.0：安全、隐私、恢复与可诊断性

**目标：** 补齐桌面邮件客户端最容易被忽略、但最影响信任的安全和恢复能力。  
**原则：** 本阶段优先级高于插件系统、PGP、跨平台。

---

## T3.1 HTML 邮件安全查看器

**优先级：P0**

### 目标
默认阻止外部追踪与高风险内容。

### 涉及文件
- `src/openemail/ui/mail/mail_view.py`
- `src/openemail/ui/resources/`
- 相关安全测试

### 执行内容
1. 默认禁用远程图片加载。
2. 默认禁用脚本执行。
3. 禁止本地文件越权访问。
4. 显示“外部内容已阻止”的提示栏。
5. 提供“临时加载外部内容”的受控入口。
6. 保证纯文本回退可用。

### 验收标准
- 打开 HTML 邮件不会默认向第三方发请求
- 恶意 HTML fixture 不会直接执行危险行为

### 验证命令
```bash
pytest -k "html or mail_view or security" -q
```

### 推荐提交信息
```bash
git commit -m "phase3: add safe HTML mail rendering policy"
```

---

## T3.2 凭据、token 与设置存储加固

**优先级：P0**

### 目标
敏感数据只存该存的地方，日志和设置中不留隐患。

### 涉及文件
- `src/openemail/utils/crypto.py`
- `src/openemail/core/oauth2_new.py`
- `src/openemail/config.py`
- `tests/test_crypto.py`

### 执行内容
1. 密码与 token 通过 keyring + 加密层保存。
2. settings 文件不保存明文秘密。
3. 明确 OAuth 凭据文件的作用与格式。
4. 对凭据缺失、损坏、过期提供恢复路径。

### 验收标准
- 普通设置文件中没有明文密码或 token
- 凭据损坏时不会导致应用直接崩溃

### 验证命令
```bash
pytest tests/test_crypto.py tests/test_oauth2.py -q
```

### 推荐提交信息
```bash
git commit -m "phase3: harden credential and token storage"
```

---

## T3.3 诊断包与可共享日志导出

**优先级：P1**

### 目标
用户报告问题时，能导出一份“有用但不泄密”的诊断包。

### 涉及文件
- `src/openemail/ui/tools/`
- `src/openemail/app.py`
- `src/openemail/utils/`

### 执行内容
1. 增加“导出诊断包”功能。
2. 包含：
   - 应用版本
   - 操作系统信息
   - 启用的功能标记
   - 最近脱敏日志
   - 数据库/索引健康摘要
3. 默认不包含：
   - 明文密码
   - token
   - 邮件正文全文
   - 完整附件内容

### 验收标准
- 用户可直接把诊断包附到 issue
- 导出的内容可用于排障但不暴露核心敏感数据

### 验证命令
```bash
python -m openemail.main --debug
```

### 推荐提交信息
```bash
git commit -m "phase3: add sanitized diagnostic export"
```

---

## T3.4 备份、恢复与索引重建入口

**优先级：P0**

### 目标
用户不应该因为一次索引损坏或数据库问题就被迫删库重来。

### 涉及文件
- `src/openemail/ui/settings/`
- `src/openemail/storage/`
- 恢复与备份相关脚本/工具

### 执行内容
1. 增加数据库备份入口。
2. 增加从备份恢复入口。
3. 增加只重建索引、不动原始邮件数据的入口。
4. 恢复失败时输出明确错误信息。

### 验收标准
- 用户可做手动备份
- 索引损坏时可局部修复

### 验证命令
```bash
pytest -k "database or migration or search" -q
```

### 推荐提交信息
```bash
git commit -m "phase3: add backup restore and index rebuild entrypoints"
```

---

# Phase 4 — v1.0.0 前收口：PIM 边界、体验收口、发布准备

**目标：** 在不扩大战线的前提下，把已有 PIM 能力和整体体验收口，准备正式发布。  
**原则：** 不求面广，求清晰、可用、可维护。

---

## T4.1 PIM 范围收口与状态重标

**优先级：P0**

### 目标
明确 Calendar、Contacts、Todo、Projects 到底属于 Stable、Beta 还是 Experimental。

### 涉及文件
- `README.md`
- `docs/feature-matrix.md`
- `SUPPORTED.md`
- 各对应模块 UI 文案

### 执行内容
1. Calendar：若 CalDAV 链路可用，则保留 Beta；否则降级为 Experimental。
2. Contacts：如果只有本地 CRUD，也要写清楚“本地优先，非同步联系人系统”。
3. Todo / Projects：若没有完善测试与数据模型稳定性，统一降级为 Beta/Experimental。
4. 更新所有入口文案与 README。

### 验收标准
- 用户一看就知道 PIM 各模块的真实成熟度

### 推荐提交信息
```bash
git commit -m "phase4: re-scope PIM modules for 1.0 release"
```

---

## T4.2 Calendar 与 Contacts 最小可用打磨

**优先级：P1**

### 目标
不追求全能，但至少做到“基础可用”。

### 涉及文件
- `src/openemail/ui/calendar/calendar_page.py`
- `src/openemail/core/caldav_client.py`
- `src/openemail/ui/contacts/`
- `tests/` 中相关测试

### 执行内容
1. Calendar：确认创建、编辑、删除、提醒可用。
2. Contacts：确认新增、编辑、搜索可用。
3. 如可能，增加导入导出：
   - 联系人：vCard
   - 日历：ICS
4. 至少补少量 smoke 测试。

### 验收标准
- 日历和联系人不是“点进去就像半成品”

### 推荐提交信息
```bash
git commit -m "phase4: polish minimum usable calendar and contacts flows"
```

---

## T4.3 设置页、状态中心与 onboarding 收口

**优先级：P0**

### 目标
让用户知道当前 app 处于什么状态，而不是在失败时一脸懵。

### 涉及文件
- `src/openemail/ui/settings/settings_page.py`
- `src/openemail/ui/main_window.py`
- `src/openemail/ui/mail/welcome_dialog.py`
- `src/openemail/ui/mail/welcome_dialog_enhanced.py`

### 执行内容
1. 增加统一状态展示：
   - 正在同步
   - 离线
   - 授权过期
   - 队列积压
   - 恢复可用
2. onboarding 中说明：
   - 支持的 provider
   - OAuth2 / app password 差异
   - 隐私与外部内容策略
3. 设置页补齐：
   - 搜索索引重建
   - 诊断包导出
   - 语义搜索开关
   - 通知开关

### 验收标准
- 新用户初次启动时不会完全无所适从
- 失败状态有可见反馈

### 推荐提交信息
```bash
git commit -m "phase4: unify onboarding settings and runtime status UX"
```

---

## T4.4 发布文档包

**优先级：P0**

### 目标
在正式发布前，文档必须足够支撑用户安装、配置、排障和贡献。

### 涉及文件
- `README.md`
- `docs/user-guide.md`（新建）
- `docs/developer-guide.md`（新建）
- `CONTRIBUTING.md`（新建或重写）
- `MAINTENANCE.md`（新建）

### 执行内容
1. 用户手册：安装、账号配置、搜索、草稿、离线、恢复、故障排查。
2. 开发者手册：架构、运行、测试、打包、日志、迁移。
3. 贡献指南：PR 规范、测试要求、提交规范。
4. 维护指南：发布流程、支持边界、版本策略。

### 验收标准
- 新用户和新贡献者都能靠文档完成基本操作

### 推荐提交信息
```bash
git commit -m "phase4: add user developer and maintenance docs"
```

---

# Phase 5 — v1.0.0：正式发布门禁与收尾

**目标：** 在打 tag 之前，确认产品真的达到“可发布”标准。  
**原则：** 没达到门禁，就不要打 1.0。

---

## T5.1 回归测试总表与手工 smoke checklist

**优先级：P0**

### 目标
建立正式发布前必须跑的一整套清单。

### 建议清单
至少覆盖以下场景：

1. Gmail OAuth2 新增账户
2. Outlook OAuth2 新增账户
3. Generic IMAP/SMTP 新增账户
4. 首次同步 Inbox
5. 增量同步后状态变化正常
6. 搜索 `from:`、`subject:`、`has:attachment`
7. 撰写邮件并发送附件
8. 自动保存草稿后恢复
9. 离线撰写并重连自动发送
10. HTML 邮件默认阻止外部内容
11. 崩溃恢复对话框可触发
12. 备份、恢复、重建索引入口可用
13. AppImage / Flatpak 可启动

### 产出物
- `docs/release-checklist.md`
- `docs/manual-smoke.md`

### 推荐提交信息
```bash
git commit -m "phase5: add release regression and smoke checklist"
```

---

## T5.2 发布材料与 issue 模板

**优先级：P1**

### 目标
让发布之后的反馈有组织、有结构。

### 涉及文件
- `.github/ISSUE_TEMPLATE/`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `CHANGELOG.md`
- GitHub Release 模板

### 执行内容
1. 建立 bug report 模板。
2. 建立 auth/provider bug 模板。
3. 建立 crash report 模板。
4. 更新 `CHANGELOG.md` 到 v1.0.0。

### 推荐提交信息
```bash
git commit -m "phase5: add release templates and changelog updates"
```

---

## T5.3 v1.0.0 发布门禁

**必须全部满足，才允许打 tag：**

1. README / SUPPORTED / KNOWN_LIMITATIONS / feature matrix 已同步
2. CI 全绿
3. Gmail / Outlook / Generic IMAP 三条主链路 smoke 通过
4. Drafts / Sent / Search / Offline Queue 稳定
5. HTML 安全查看器生效
6. 日志脱敏生效
7. 备份 / 恢复 / 索引重建可用
8. Linux 包可安装运行
9. 无已知 P0 数据丢失 bug
10. 过去一轮 Beta 中阻塞问题已清空

### 推荐收尾命令
```bash
git tag v1.0.0
git push --tags
```

---

# 5. 建议延后到 1.0 之后的事项

以下内容建议全部放到 1.1 以后再做，不进入本 roadmap 主线：

1. ActiveSync 全量产品化或 Graph API 重构
2. PGP / S/MIME
3. 插件系统
4. Windows 适配
5. macOS 适配
6. CardDAV 深度支持
7. 默认语义搜索
8. 高级项目管理工作流

---

# 6. AI 每轮执行输出模板

建议要求 AI 每完成一个任务，都按下面格式输出：

```text
任务：T0.1

修改文件：
- ...
- ...

完成内容：
- ...
- ...

验证命令：
- ...
- ...

验证结果：
- pass / fail

风险与说明：
- ...

建议下一步：
- T0.2
```

---

---

# 8. 最后的建议

如果你准备把这份 roadmap 交给 AI 连续执行，最稳妥的方式不是一口气让它“做完 v1.0”，而是：

1. 一次只给它一个任务卡
2. 每次都要求它运行验证命令
3. 每完成 3 到 5 个任务，人工审一次 README、diff 和测试结果
4. 遇到“功能看起来很大”的任务时，先让 AI 进一步拆成 2 到 4 个子任务再做

这样项目会稳很多，也更不容易被 AI 带偏。
