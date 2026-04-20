SCHEMA_VERSION = 11

MIGRATIONS: dict[int, list[str]] = {
    1: [
        """CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        )""",
        """CREATE TABLE IF NOT EXISTS accounts (
            id              INTEGER PRIMARY KEY,
            name            TEXT NOT NULL,
            email           TEXT NOT NULL UNIQUE,
            protocol        TEXT NOT NULL DEFAULT 'imap',
            imap_host       TEXT,
            imap_port       INTEGER DEFAULT 993,
            pop3_host       TEXT,
            pop3_port       INTEGER DEFAULT 995,
            smtp_host       TEXT,
            smtp_port       INTEGER DEFAULT 465,
            ssl_mode        TEXT DEFAULT 'ssl',
            auth_type       TEXT DEFAULT 'password',
            oauth_provider  TEXT,
            is_active       INTEGER DEFAULT 1,
            last_sync_at    TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS folders (
            id            INTEGER PRIMARY KEY,
            account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            name          TEXT NOT NULL,
            path          TEXT,
            unread_count  INTEGER DEFAULT 0,
            is_system     INTEGER DEFAULT 0,
            UNIQUE(account_id, name)
        )""",
        """CREATE TABLE IF NOT EXISTS emails (
            id             INTEGER PRIMARY KEY,
            account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            folder_id      INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            uid            TEXT,
            message_id     TEXT,
            subject        TEXT,
            sender_name    TEXT,
            sender_addr    TEXT,
            to_addrs       TEXT,
            cc_addrs       TEXT,
            bcc_addrs      TEXT,
            date           TEXT,
            size           INTEGER,
            is_read        INTEGER DEFAULT 0,
            is_flagged     INTEGER DEFAULT 0,
            is_deleted     INTEGER DEFAULT 0,
            is_spam        INTEGER DEFAULT 0,
            spam_reason    TEXT,
            has_attachment INTEGER DEFAULT 0,
            preview_text   TEXT,
            file_path      TEXT,
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, folder_id, uid)
        )""",
        """CREATE TABLE IF NOT EXISTS filter_rules (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            rule_type   TEXT NOT NULL,
            pattern     TEXT,
            is_enabled  INTEGER DEFAULT 1,
            priority    INTEGER DEFAULT 0,
            action      TEXT DEFAULT 'move_spam',
            hit_count   INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS bayes_tokens (
            token       TEXT PRIMARY KEY,
            spam_count  INTEGER DEFAULT 0,
            ham_count   INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS contacts (
            id          INTEGER PRIMARY KEY,
            account_id  INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            name        TEXT,
            email       TEXT NOT NULL,
            phone       TEXT,
            notes       TEXT,
            avatar_path TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS calendar_events (
            id              INTEGER PRIMARY KEY,
            account_id      INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            title           TEXT NOT NULL,
            description     TEXT,
            location        TEXT,
            start_time      TEXT NOT NULL,
            end_time        TEXT,
            is_all_day      INTEGER DEFAULT 0,
            recurrence      TEXT,
            reminder        INTEGER,
            color           TEXT,
            email_uid       TEXT,
            sync_enabled    INTEGER DEFAULT 0,
            sync_provider   TEXT,
            sync_url        TEXT,
            sync_etag       TEXT,
            last_synced_at  TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS todos (
            id              INTEGER PRIMARY KEY,
            account_id      INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            title           TEXT NOT NULL,
            description     TEXT,
            status          TEXT DEFAULT 'pending',
            priority        TEXT DEFAULT 'normal',
            due_date        TEXT,
            reminder        INTEGER,
            tags            TEXT,
            email_uid       TEXT,
            sync_enabled    INTEGER DEFAULT 0,
            sync_provider   TEXT,
            sync_url        TEXT,
            sync_etag       TEXT,
            last_synced_at  TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            color       TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS project_columns (
            id          INTEGER PRIMARY KEY,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            position    INTEGER DEFAULT 0,
            UNIQUE(project_id, name)
        )""",
        """CREATE TABLE IF NOT EXISTS project_cards (
            id          INTEGER PRIMARY KEY,
            column_id   INTEGER NOT NULL REFERENCES project_columns(id) ON DELETE CASCADE,
            title       TEXT NOT NULL,
            description TEXT,
            position    INTEGER DEFAULT 0,
            priority    TEXT DEFAULT 'normal',
            due_date    TEXT,
            tags        TEXT,
            assignee    TEXT,
            email_uid   TEXT,
            todo_id     INTEGER REFERENCES todos(id) ON DELETE SET NULL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE INDEX IF NOT EXISTS idx_emails_account_folder
            ON emails(account_id, folder_id)""",
        """CREATE INDEX IF NOT EXISTS idx_emails_uid
            ON emails(account_id, uid)""",
        """CREATE INDEX IF NOT EXISTS idx_emails_sender
            ON emails(sender_addr)""",
        """CREATE INDEX IF NOT EXISTS idx_emails_date
            ON emails(date)""",
        """CREATE INDEX IF NOT EXISTS idx_emails_is_spam
            ON emails(is_spam)""",
        """CREATE INDEX IF NOT EXISTS idx_filter_rules_type
            ON filter_rules(rule_type)""",
        """CREATE INDEX IF NOT EXISTS idx_todos_status
            ON todos(status)""",
        """CREATE INDEX IF NOT EXISTS idx_calendar_events_start
            ON calendar_events(start_time)""",
        """CREATE INDEX IF NOT EXISTS idx_project_cards_column
            ON project_cards(column_id)""",
    ],
    2: [
        """ALTER TABLE accounts ADD COLUMN password_enc TEXT DEFAULT ''""",
        """ALTER TABLE accounts ADD COLUMN oauth_token_enc TEXT DEFAULT ''""",
        """ALTER TABLE accounts ADD COLUMN oauth_refresh_enc TEXT DEFAULT ''""",
    ],
    3: [
        # 标签表
        """CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#89b4fa',
            icon TEXT DEFAULT '🏷️'
        )""",
        # 邮件 - 标签关联表
        """CREATE TABLE IF NOT EXISTS email_tags (
            email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
            tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (email_id, tag_id)
        )""",
        # 文件夹嵌套支持
        """ALTER TABLE folders ADD COLUMN parent_id INTEGER REFERENCES folders(id)""",
        """ALTER TABLE folders ADD COLUMN delimiter TEXT DEFAULT '/'""",
        # FTS5 全文搜索
        """CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            subject, sender_name, sender_addr, preview_text,
            content='emails', content_rowid='id'
        )""",
        # FTS 触发器
        """CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
            INSERT INTO emails_fts(rowid, subject, sender_name, sender_addr, preview_text)
            VALUES (new.id, new.subject, new.sender_name, new.sender_addr, new.preview_text);
        END""",
        """CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
            DELETE FROM emails_fts WHERE rowid=old.id;
        END""",
        """CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
            UPDATE emails_fts SET
                subject=new.subject,
                sender_name=new.sender_name,
                sender_addr=new.sender_addr,
                preview_text=new.preview_text
            WHERE rowid=old.id;
        END""",
        # 操作队列表（离线支持）
        """CREATE TABLE IF NOT EXISTS operation_queue (
            id INTEGER PRIMARY KEY,
            account_id INTEGER REFERENCES accounts(id),
            operation_type TEXT NOT NULL,
            email_uid TEXT,
            folder_name TEXT,
            params TEXT,
            status TEXT DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        # 过滤规则增强
        """ALTER TABLE filter_rules ADD COLUMN match_field TEXT DEFAULT 'all'""",
        """ALTER TABLE filter_rules ADD COLUMN action_target TEXT""",
        # 索引
        """CREATE INDEX IF NOT EXISTS idx_email_tags_email ON email_tags(email_id)""",
        """CREATE INDEX IF NOT EXISTS idx_email_tags_tag ON email_tags(tag_id)""",
        """CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id)""",
        """CREATE INDEX IF NOT EXISTS idx_operation_queue_status ON operation_queue(status)""",
    ],
    4: [
        # 添加ActiveSync支持字段
        """ALTER TABLE accounts ADD COLUMN eas_host TEXT""",
        """ALTER TABLE accounts ADD COLUMN eas_path TEXT DEFAULT '/Microsoft-Server-ActiveSync'""",
        # 添加日历和联系人同步字段
        """ALTER TABLE accounts ADD COLUMN sync_calendar INTEGER DEFAULT 0""",
        """ALTER TABLE accounts ADD COLUMN sync_contacts INTEGER DEFAULT 0""",
        """ALTER TABLE accounts ADD COLUMN sync_tasks INTEGER DEFAULT 0""",
        # 设备ID字段用于ActiveSync
        """ALTER TABLE accounts ADD COLUMN eas_device_id TEXT""",
        # 为ActiveSync添加索引
        """CREATE INDEX IF NOT EXISTS idx_accounts_protocol ON accounts(protocol)""",
    ],
    5: [
        # 批次 D：连接状态状态机和验证字段
        """ALTER TABLE accounts ADD COLUMN connection_status TEXT DEFAULT 'unverified'""",
        """ALTER TABLE accounts ADD COLUMN token_expires_at TEXT""",
        """ALTER TABLE accounts ADD COLUMN last_error_code TEXT""",
        """ALTER TABLE accounts ADD COLUMN last_error_at TEXT""",
        """ALTER TABLE accounts ADD COLUMN sync_fail_count INTEGER DEFAULT 0""",
        """ALTER TABLE accounts ADD COLUMN last_verified_at TEXT""",
        """ALTER TABLE accounts ADD COLUMN validation_result TEXT""",
        """ALTER TABLE accounts ADD COLUMN is_default INTEGER DEFAULT 0""",
        # 为连接状态和最后验证时间添加索引
        """CREATE INDEX IF NOT EXISTS idx_accounts_connection_status ON accounts(connection_status)""",
        """CREATE INDEX IF NOT EXISTS idx_accounts_last_verified ON accounts(last_verified_at)""",
        """CREATE INDEX IF NOT EXISTS idx_accounts_sync_fail ON accounts(sync_fail_count)""",
        """CREATE INDEX IF NOT EXISTS idx_accounts_is_default ON accounts(is_default)""",
        # 迁移历史数据
        """UPDATE accounts SET connection_status = 'verified' WHERE is_active = 1""",
        """UPDATE accounts SET connection_status = 'disabled' WHERE is_active = 0""",
        """UPDATE accounts SET last_verified_at = datetime('now') WHERE connection_status = 'verified'""",
        # 批次 D2：设置第一个已验证账号为默认
        """UPDATE accounts SET is_default = 1 WHERE id IN (
            SELECT id FROM accounts 
            WHERE is_active = 1 AND connection_status IN ('verified', 'sync_ready') 
            ORDER BY id LIMIT 1
        )""",
    ],
    6: [
        # 批次 E-F：OAuth和验证增强
        """ALTER TABLE accounts ADD COLUMN metadata TEXT DEFAULT ''""",
        # 为metadata添加注释：JSON序列化的元数据，用于存储风险信息等
    ],
    7: [
        # RFC 6154 SPECIAL-USE 支持
        """ALTER TABLE folders ADD COLUMN special_use TEXT DEFAULT ''""",
        """CREATE INDEX IF NOT EXISTS idx_folders_special_use ON folders(account_id, special_use)""",
    ],
    8: [
        # 草稿自动保存
        """CREATE TABLE IF NOT EXISTS drafts (
            id              INTEGER PRIMARY KEY,
            account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            folder_id       INTEGER REFERENCES folders(id) ON DELETE SET NULL,
            message_id      TEXT,
            uid             TEXT,
            from_addr       TEXT NOT NULL,
            to_addrs        TEXT DEFAULT '',
            cc_addrs        TEXT DEFAULT '',
            bcc_addrs       TEXT DEFAULT '',
            subject         TEXT DEFAULT '',
            body_text       TEXT DEFAULT '',
            body_html       TEXT DEFAULT '',
            attachments     TEXT DEFAULT '{}',
            in_reply_to     TEXT DEFAULT '',
            "references"    TEXT DEFAULT '',
            is_local_only   INTEGER DEFAULT 1,
            is_syncing      INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            synced_at       TEXT,
            UNIQUE(account_id, message_id)
        )""",
        """CREATE INDEX IF NOT EXISTS idx_drafts_account ON drafts(account_id, updated_at)""",
        """CREATE INDEX IF NOT EXISTS idx_drafts_sync ON drafts(is_local_only, is_syncing)""",
    ],
    9: [
        # OAuth2 token cache 持久化
        """CREATE TABLE IF NOT EXISTS oauth_tokens (
            id              INTEGER PRIMARY KEY,
            account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            provider        TEXT NOT NULL,
            access_token    TEXT NOT NULL,
            refresh_token   TEXT DEFAULT '',
            token_type      TEXT DEFAULT 'Bearer',
            scope           TEXT DEFAULT '',
            expires_at      TEXT,
            created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, provider)
        )""",
    ],
    10: [
        # Email threading support
        """ALTER TABLE emails ADD COLUMN in_reply_to TEXT DEFAULT ''""",
        """ALTER TABLE emails ADD COLUMN "references" TEXT DEFAULT ''""",
        """CREATE TABLE IF NOT EXISTS email_threads (
            id              INTEGER PRIMARY KEY,
            account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            subject         TEXT DEFAULT '',
            message_count   INTEGER DEFAULT 1,
            last_date       TEXT,
            created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS email_thread_members (
            id              INTEGER PRIMARY KEY,
            thread_id       INTEGER NOT NULL REFERENCES email_threads(id) ON DELETE CASCADE,
            email_id        INTEGER NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
            UNIQUE(thread_id, email_id)
        )""",
        """CREATE INDEX IF NOT EXISTS idx_threads_account ON email_threads(account_id, last_date)""",
        """CREATE INDEX IF NOT EXISTS idx_thread_members_thread ON email_thread_members(thread_id)""",
        """CREATE INDEX IF NOT EXISTS idx_thread_members_email ON email_thread_members(email_id)""",
        """CREATE INDEX IF NOT EXISTS idx_emails_in_reply_to ON emails(in_reply_to)""",
    ],
    11: [
        # Bayesian spam filter
        """CREATE TABLE IF NOT EXISTS bayes_tokens (
            token       TEXT PRIMARY KEY,
            spam_count  INTEGER DEFAULT 0,
            ham_count   INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS bayes_meta (
            id          INTEGER PRIMARY KEY,
            spam_count  INTEGER DEFAULT 0,
            ham_count   INTEGER DEFAULT 0
        )""",
        """CREATE INDEX IF NOT EXISTS idx_bayes_spam ON bayes_tokens(spam_count)""",
        """CREATE INDEX IF NOT EXISTS idx_bayes_ham ON bayes_tokens(ham_count)""",
    ],
}
