# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - Unreleased

### Added
- Feature matrix and support status documentation (`docs/feature-matrix.md`, `SUPPORTED.md`, `KNOWN_LIMITATIONS.md`).
- Baseline CI workflow with ruff lint, pytest, and multi-version Python matrix.
- Centralized logging with sensitive data redaction (tokens, passwords, authorization headers).
- Shared test fixtures and sample mail builders in `tests/conftest.py` and `tests/fixtures/`.
- Database migration rollback and pre-migration backup.
- Crash recovery groundwork: crash flag detection, queue replay, and recovery dialog.
- Unified authentication interface with `ensure_auth()` for IMAP and SMTP.
- Connection tester with status machine and UI integration (verified / auth_failed / network_failed).
- Auto-sync on startup with periodic timer (5 min interval); removed manual sync button.
- Folder discovery with RFC 6154 SPECIAL-USE mapping and provider prefix resolution.
- Folder reconciliation: handles new, renamed, deleted folders on sync.
- UIDVALIDITY tracking and high-water mark for incremental sync correctness.
- Sync correctness test suite covering flag sync, deduplication, and interruption recovery.
- Dark mode theme overhaul with warm neutral palette and global theme enforcer.
- UI component spec overhaul: buttons, inputs, cards, tags.
- Sidebar two-level hierarchy with collapsible sections.

### Changed
- Version bumped from 0.1.0 to 0.6.0 to reflect actual development stage.
- Optional dependencies split into extras: `oauth`, `semantic`, `spam`, `dev`, `all`.
- `print()` statements replaced with structured logging across the codebase.
- SQL INSERT/UPDATE now quotes column names to handle reserved words (e.g., `references`).
- Mail sync loop logging upgraded from `debug` to `info`/`warning` for observability.

### Fixed
- Bare `except:` clauses replaced with specific exception handling.
- OAuth widget initialization order bug in account dialog.
- Compose window button clipping and hardcoded inline colors.
- Theme color consistency across light and dark modes.
- `MailSyncManager` singleton `QObject` initialization ordering.

## [0.1.0] - 2025-04-11

### Added
- Initial project structure with PyQt6 desktop email client.
- Basic IMAP/SMTP client with synchronous fallback wrapper.
- Multi-account management with provider presets (Gmail, Outlook, Generic).
- OAuth2 authorization flow (Google, Microsoft).
- Local SQLite storage for emails, folders, accounts, and settings.
- Basic mail list, mail view, and compose window.
- Simple Bayesian spam filter (Chinese/English).
- FTS5 full-text search.
- Calendar and contacts modules (local CRUD).
- TODO and project board modules (experimental).
