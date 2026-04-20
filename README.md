# OpenEmail

A modern, open-source Linux desktop email client built with Python and PyQt6.

OpenEmail integrates email, calendar, contacts, todos, and project management into a single native desktop application — designed for Linux users who want a fast, privacy-respecting alternative to web-based mail clients.

## Features

### Email

- **Multi-protocol support** — IMAP, POP3, and Exchange ActiveSync
- **Multiple authentication** — Plain password, app-specific password, and OAuth2 (Google / Microsoft)
- **Provider presets** — One-click setup for Gmail, Outlook, Yahoo, 163, QQ, and more
- **Connection testing** — Real-time validation of server settings before saving an account
- **Offline queue** — Compose and manage emails offline; auto-send when connectivity returns
- **Attachment management** — Add, preview, and manage attachments with a dedicated UI
- **Enhanced search** — Full-text search with filters (sender, date range, label, read/unread)
- **Spam filtering** — Built-in Bayesian spam classifier with Chinese (jieba) tokenization support
- **Mail sync** — Background sync with configurable interval; per-account status tracking

### PIM (Personal Information Management)

- **Calendar** — Month / week / day views; create and manage events
- **Contacts** — Full contact manager with detail view and editor
- **Todos** — Priority-based task management with kanban-style columns (urgent / high / normal / low)
- **Projects** — Lightweight project boards for organizing work
- **Labels** — Flexible labeling system with color-coded selectors

### UI & Theming

- **Dark and Light themes** — Catppuccin-inspired palettes, follows system preference by default
- **Sidebar navigation** — Quick access to all modules
- **Compose window** — Rich formatting with attachment support
- **Desktop entry** — Integrates with Linux application launchers

### Robustness

- **Graceful dependency fallback** — Falls back to Python stdlib (`imaplib`, `smtplib`) when async libraries (`aioimaplib`, `aiosmtplib`) are unavailable
- **Crash detection & recovery** — Detects abnormal exits on next launch and logs diagnostics
- **Global exception handler** — Catches unhandled exceptions to prevent silent crashes
- **Connection state machine** — Accounts track their connection status (unverified → verified → sync_ready, with auth_failed / network_failed / disabled states)
- **Encrypted credential storage** — Passwords and OAuth tokens encrypted at rest via `cryptography` + `keyring`

## Requirements

- Python >= 3.11
- PyQt6 >= 6.11
- Linux (X11 or Wayland)

## Installation

### From source

```bash
git clone https://github.com/Lcryolite/homing.git
cd homing
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
├── main.py                  # Entry point
├── app.py                   # QApplication setup, theme, crash detection
├── config.py                # Settings management
├── core/
│   ├── imap_client.py       # IMAP client (async + stdlib fallback)
│   ├── pop3_client.py       # POP3 client
│   ├── smtp_client.py       # SMTP client (async + stdlib fallback)
│   ├── activesync_client.py # Exchange ActiveSync client
│   ├── oauth2.py            # OAuth2 authenticator (legacy)
│   ├── oauth2_new.py        # OAuth2 manager with structured error codes
│   ├── mail_sync.py         # Background mail sync worker
│   ├── connection_status.py # Account connection state machine
│   ├── connection_tester.py # Multi-protocol connection tester
│   ├── validation_snapshot.py # Form validation snapshot system
│   ├── account_cleanup.py   # Account cleanup utilities
│   ├── operation_queue.py   # Async operation queue
│   ├── network_monitor.py   # Network connectivity monitor
│   ├── mail_builder.py      # Outgoing email builder
│   └── mail_parser.py       # Incoming email parser
├── models/
│   ├── account.py           # Account model with provider presets
│   ├── email.py             # Email model
│   ├── folder.py            # Folder model
│   ├── contact.py           # Contact model
│   ├── calendar_event.py    # Calendar event model
│   ├── todo.py              # Todo model
│   ├── project.py           # Project model
│   ├── label.py             # Label model
│   ├── tag.py               # Tag model
│   └── filter_rule.py       # Filter rule model
├── storage/
│   ├── database.py          # SQLite database layer
│   ├── migrations.py        # Schema migrations
│   ├── mail_store.py        # Email storage operations
│   ├── search.py            # Basic search
│   └── search_enhanced.py   # Enhanced full-text search
├── filter/
│   ├── engine.py            # Filter engine
│   ├── enhanced_filter_engine.py # Enhanced filter with complex rules
│   ├── rule_matcher.py      # Rule matching
│   └── tokenizer.py         # Text tokenizer (Bayesian + jieba)
├── queue/
│   ├── email_operations.py  # Email operation definitions
│   └── offline_queue.py     # Offline operation queue
├── ui/
│   ├── main_window.py       # Main application window
│   ├── sidebar.py           # Sidebar navigation
│   ├── accounts_dialog.py   # Accounts management dialog
│   ├── mail/
│   │   ├── account_dialog.py     # Account add/edit with connection testing
│   │   ├── compose_window.py     # Email compose window
│   │   ├── mail_list.py         # Mail list view
│   │   ├── mail_list_enhanced.py # Enhanced mail list with threading
│   │   ├── mail_view.py         # Email content viewer
│   │   ├── search_bar.py        # Search bar widget
│   │   ├── attachment_manager.py # Attachment manager
│   │   ├── attachment_preview.py # Attachment preview
│   │   ├── welcome_dialog.py    # Welcome/onboarding dialog
│   │   └── welcome_dialog_enhanced.py # Enhanced welcome dialog
│   ├── calendar/
│   │   └── calendar_page.py # Calendar with month/week/day views
│   ├── contacts/
│   │   ├── contact_page.py    # Contacts page
│   │   ├── contact_detail.py  # Contact detail view
│   │   ├── contact_editor.py  # Contact editor form
│   │   └── contact_manager.py # Contact management logic
│   ├── todo/
│   │   └── todo_page.py     # Todo with kanban columns
│   ├── project/
│   │   └── project_page.py  # Project board
│   ├── labels/
│   │   ├── label_manager.py  # Label management
│   │   └── label_selector.py # Label selector widget
│   ├── filter/
│   │   ├── filter_dialog.py         # Filter rule dialog
│   │   └── enhanced_filter_manager.py # Enhanced filter manager UI
│   ├── search/
│   │   └── search_enhanced_ui.py # Enhanced search UI
│   ├── settings/
│   │   ├── settings_page.py   # Settings page
│   │   └── account_settings.py # Account-specific settings
│   ├── queue/
│   │   └── offline_queue_manager.py # Offline queue UI
│   └── resources/
│       └── styles/
│           ├── dark.qss      # Dark theme (Catppuccin Mocha)
│           └── light.qss     # Light theme (Catppuccin Latte)
└── utils/
    ├── crypto.py             # Password encryption/decryption
    ├── exceptions.py         # Custom exception hierarchy
    └── notify.py             # Desktop notifications
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

> **Note:** If async libraries (`aioimaplib`, `aiosmtplib`) are not installed, OpenEmail automatically falls back to Python's standard library `imaplib`/`smtplib` with a synchronous-to-async wrapper.

## Testing

```bash
pip install pytest
pytest
```

## License

[GNU General Public License v3.0 or later](LICENSE)
