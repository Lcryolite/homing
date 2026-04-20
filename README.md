# OpenEmail

A modern, open-source Linux desktop email client built with Python and PyQt6.

OpenEmail integrates email, calendar, contacts, todos, and project management into a single native desktop application — designed for Linux users who want a fast, privacy-respecting alternative to web-based mail clients.

**Current version:** v0.5.0 | **License:** GPL-3.0-or-later

## Features

### Email

- **Multi-protocol support** — IMAP and POP3 (receiving), SMTP (sending); Exchange ActiveSync is an experimental stub (see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md))
- **Multiple authentication** — Plain password, app-specific password, and OAuth2 (Google / Microsoft)
- **Provider presets** — One-click setup for Gmail, Outlook, Yahoo, 163, QQ, and more
- **Connection testing** — Real-time validation of server settings before saving an account; granular error classification (10 categories) with diagnostic suggestions
- **Offline queue** — Compose and manage emails offline; auto-send when connectivity returns
- **Draft auto-save** — Local autosave with IMAP APPEND sync to \Drafts folder
- **Attachment management** — Add, preview, and manage attachments with a dedicated UI
- **Email threading** — Conversation view with THREAD=REFERENCES support and local fallback
- **Enhanced search** — FTS5 full-text search with advanced filters (from:, to:, subject:, has:, is:, after:, before:, in:), snippet highlighting, search history, and suggestions
- **Semantic search** — Sentence Transformers + Faiss vector similarity search with reranking
- **Spam filtering** — Built-in Bayesian spam classifier with Chinese (jieba) tokenization; trainable with unsure middle state and correction feedback loop
- **Mail sync** — Background sync with configurable interval; per-account status tracking
- **Rich text editor** — Compose emails with formatting toolbar (bold, italic, lists, links, etc.)
- **Filter rules** — Enhanced rule engine with AND/OR logic, multiple condition types, priority, import/export

### PIM (Personal Information Management)

- **Calendar** — Month / week / day views; create and manage events with color coding; CalDAV sync support; D-Bus desktop reminders
- **Contacts** — Full contact manager with detail view and editor
- **Todos** — Priority-based task management (today / week / all views); overdue detection
- **Projects** — Lightweight kanban-style project boards with cards, columns, and drag reordering
- **Labels** — Flexible labeling system with color-coded selectors

### UI & Theming

- **Dark and Light themes** — Catppuccin-inspired palettes, follows system preference by default
- **Sidebar navigation** — Quick access to all modules with icons and compose button
- **Toolbar** — Sync, compose, and add-account actions at top level
- **Keyboard shortcuts** — Application-wide shortcut system with help dialog (Ctrl+?)
- **Settings page** — In-app settings for theme, accounts, sync, filter rules
- **Desktop entry** — Integrates with Linux application launchers

### Robustness

- **Graceful dependency fallback** — Falls back to Python stdlib (`imaplib`, `smtplib`) when async libraries (`aioimaplib`, `aiosmtplib`) are unavailable
- **Crash detection & recovery** — Detects abnormal exits on next launch and logs diagnostics
- **Global exception handler** — Catches unhandled exceptions to prevent silent crashes
- **Connection state machine** — Accounts track their connection status (unverified → verified → sync_ready, with auth_failed / network_failed / disabled states)
- **Encrypted credential storage** — Passwords and OAuth tokens encrypted at rest via `cryptography` + `keyring`
- **Account cleanup** — Diagnostic tool for inspecting account status and cleaning up dirty accounts
- **Background task manager** — Daemon thread management for calendar reminders and semantic indexing

## Requirements

- Python >= 3.11
- PyQt6 >= 6.11
- PyQt6-WebEngine >= 6.11
- Linux (X11 or Wayland)

## Installation

### From source

```bash
git clone https://github.com/Lcryolite/Open-Email.git
cd Open-Email
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run

```bash
openemail
```

Or directly:

```bash
python -m openemail.main
```

### Command-line options

```
openemail [--theme {light,dark,system}] [--debug]
```

- `--theme` — Override the theme setting (light / dark / system)
- `--debug` — Enable debug mode with verbose logging

## Configuration

OpenEmail stores all user data under `~/.openemail/`:

| Path | Description |
|---|---|
| `~/.openemail/openemail.db` | SQLite database (emails, accounts, contacts, events, etc.) |
| `~/.openemail/settings.json` | Application settings (theme, sync interval, window geometry) |
| `~/.openemail/oauth_creds.json` | OAuth2 client credentials (never commit this) |
| `~/.openemail/crash.log` | Crash diagnostic log |
| `~/.openemail/openemail.log` | Application log (if FileHandler configured) |

### Settings

| Key | Default | Description |
|---|---|---|
| `theme` | `system` | UI theme: `light`, `dark`, or `system` |
| `sync_interval_minutes` | `5` | Automatic mail sync interval |
| `onboarding_state` | `not_started` | Welcome wizard progress |

## Project Structure

```
src/openemail/
├── __init__.py
├── main.py                      # Entry point
├── app.py                       # QApplication setup, theme, crash detection
├── config.py                    # Settings management
├── core/
│   ├── imap_client.py           # IMAP client (async + stdlib fallback)
│   ├── pop3_client.py           # POP3 client
│   ├── smtp_client.py           # SMTP client (async + stdlib fallback)
│   ├── activesync_client.py     # Exchange ActiveSync client
│   ├── oauth2.py                # OAuth2 authenticator (legacy)
│   ├── oauth2_new.py            # OAuth2 manager with structured error codes
│   ├── mail_sync.py             # Background mail sync worker
│   ├── connection_status.py     # Account connection state machine
│   ├── connection_tester.py     # Multi-protocol connection tester
│   ├── connection_manager.py    # Connection lifecycle management
│   ├── validation_snapshot.py   # Form validation snapshot system
│   ├── account_cleanup.py       # Account cleanup utilities
│   ├── operation_queue.py       # Async operation queue
│   ├── network_monitor.py       # Network connectivity monitor
│   ├── mail_builder.py          # Outgoing email builder
│   ├── mail_parser.py           # Incoming email parser
│   ├── mail_helpers.py          # Shared mail utility functions
│   ├── thread_builder.py        # Email threading logic
│   ├── caldav_client.py         # CalDAV calendar sync
│   ├── draft_autosave.py        # Draft local autosave
│   └── draft_syncer.py          # Draft IMAP sync
├── models/
│   ├── account.py               # Account model with provider presets
│   ├── email.py                 # Email model
│   ├── folder.py                # Folder model (RFC 6154 SPECIAL-USE)
│   ├── contact.py               # Contact model
│   ├── calendar_event.py        # Calendar event model
│   ├── todo.py                  # Todo model
│   ├── project.py               # Project model (Project/ProjectColumn/ProjectCard)
│   ├── label.py                 # Label model
│   ├── tag.py                   # Tag model
│   └── filter_rule.py           # Filter rule model
├── storage/
│   ├── database.py              # SQLite database layer (WAL, safe APIs)
│   ├── migrations.py            # Schema migrations (versioned)
│   ├── mail_store.py            # Email storage operations
│   ├── search.py                # Basic search
│   └── search_enhanced.py       # Enhanced FTS5 + semantic search
├── filter/
│   ├── engine.py                # Basic filter engine
│   ├── enhanced_filter_engine.py # Enhanced filter with complex rules
│   ├── bayes_filter.py          # Bayesian spam classifier
│   ├── rule_matcher.py          # Rule matching
│   └── tokenizer.py             # Text tokenizer (Bayesian + jieba)
├── queue/
│   ├── email_operations.py      # Email operation definitions
│   └── offline_queue.py         # Offline operation queue
├── ui/
│   ├── main_window.py           # Main application window + toolbar
│   ├── sidebar.py               # Sidebar navigation with icons
│   ├── accounts_dialog.py       # Accounts management dialog
│   ├── mail/
│   │   ├── account_dialog.py    # Account add/edit with connection testing + OAuth
│   │   ├── compose_window.py    # Email compose window with rich text editor
│   │   ├── mail_list.py         # Mail list view
│   │   ├── mail_list_enhanced.py # Enhanced mail list with threading
│   │   ├── mail_view.py         # Email content viewer
│   │   ├── search_bar.py        # Search bar widget
│   │   ├── attachment_manager.py # Attachment manager
│   │   ├── attachment_preview.py # Attachment preview
│   │   ├── welcome_dialog.py    # Welcome/onboarding dialog
│   │   └── welcome_dialog_enhanced.py # Enhanced welcome dialog
│   ├── calendar/
│   │   └── calendar_page.py     # Calendar with month/week/day views + reminders
│   ├── contacts/
│   │   ├── contact_page.py      # Contacts page
│   │   ├── contact_detail.py    # Contact detail view
│   │   ├── contact_editor.py    # Contact editor form
│   │   └── contact_manager.py   # Contact management logic
│   ├── todo/
│   │   └── todo_page.py         # Todo with multiple view modes
│   ├── project/
│   │   └── project_page.py      # Kanban project board
│   ├── labels/
│   │   ├── label_manager.py     # Label management
│   │   └── label_selector.py    # Label selector widget
│   ├── filter/
│   │   ├── filter_dialog.py     # Filter rule dialog
│   │   └── enhanced_filter_manager.py # Enhanced filter manager UI
│   ├── search/
│   │   └── search_enhanced_ui.py # Enhanced search UI
│   ├── settings/
│   │   ├── settings_page.py     # Settings page (5 tabs)
│   │   └── account_settings.py  # Account-specific settings
│   ├── queue/
│   │   └── offline_queue_manager.py # Offline queue UI
│   ├── tools/
│   │   └── account_cleanup_dialog.py # Account diagnostic and cleanup tool
│   └── resources/
│       └── styles/
│           ├── dark.qss         # Dark theme (Catppuccin Mocha)
│           └── light.qss        # Light theme (Catppuccin Latte)
└── utils/
    ├── crypto.py                # Password encryption/decryption
    ├── exceptions.py            # Custom exception hierarchy + crash detection
    ├── notify.py                # Desktop notifications (D-Bus)
    ├── i18n.py                  # Internationalization utilities
    ├── keyboard_shortcuts.py    # Keyboard shortcut manager
    ├── calendar_reminder.py     # Calendar reminder scheduler (D-Bus)
    └── background_tasks.py      # Background task manager
```

## Dependencies

| Package | Purpose |
|---|---|
| PyQt6 | GUI framework |
| PyQt6-WebEngine | HTML email rendering |
| aioimaplib | Async IMAP client |
| aiosmtplib | Async SMTP client |
| authlib | OAuth2 authentication |
| httpx | HTTP client for OAuth2 flows |
| mail-parser | Email parsing |
| simplebayes | Bayesian spam filter |
| jieba | Chinese text segmentation |
| keyring | System keyring for secrets |
| cryptography | Password/token encryption |
| numpy | Semantic search vector operations |

> **Note:** If async libraries (`aioimaplib`, `aiosmtplib`) are not installed, OpenEmail automatically falls back to Python's standard library `imaplib`/`smtplib` with a synchronous-to-async wrapper. If `numpy` is not installed, semantic search degrades gracefully and falls back to FTS5 only.

## Testing

```bash
pip install pytest pytest-qt
pytest tests/ -v
```

Current test coverage: 46 test cases across 5 test files (smoke, connection status, database security, folder discovery, enhanced search). Coverage targets are set to 80%+ by v0.6.0 — see [ROADMAP.md](ROADMAP.md).

## Roadmap

| Version | Target | Key Goals |
|---|---|---|
| v0.5.0 | **Current** | Feature-complete: email, PIM, search, theming, semantic search, rich text |
| v0.6.0 | Production-ready | 80%+ test coverage, CI/CD, logging, packaging (AppImage/Flatpak) |
| v0.7.0 | Protocol polish | SMTP/IMAP OAuth2 complete, connection test UI, IDLE push, draft sync |
| v0.8.0 | Internationalization | Full i18n with Chinese + English, Qt Linguist workflow |
| v0.9.0 | Encryption | PGP signing/encryption, S/MIME, key management |
| v0.9.5 | Plugin system | Hook points, plugin loader, sandbox, sample plugin |
| v1.0.0 | First release | macOS/Windows support, documentation, official installers |

See [ROADMAP.md](ROADMAP.md) for the full executable task book with 138 action items.

## License

[GNU General Public License v3.0 or later](LICENSE)
