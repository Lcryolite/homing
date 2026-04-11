SCHEMA_VERSION = 3

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
}
