import email
from email import policy
from pathlib import Path

from openemail.config import settings


class MailStore:
    _instance: "MailStore | None" = None

    def __new__(cls) -> "MailStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _account_dir(self, account_id: int) -> Path:
        p = settings.mail_dir / str(account_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _folder_dir(self, account_id: int, folder: str) -> Path:
        p = self._account_dir(account_id) / folder
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _attachment_dir(self, email_id: int) -> Path:
        p = settings.attachment_dir / str(email_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_raw(self, account_id: int, folder: str, uid: str, raw: bytes) -> Path:
        folder_dir = self._folder_dir(account_id, folder)
        safe_uid = "".join(c if c.isalnum() or c in "._-" else "_" for c in str(uid))
        file_path = folder_dir / f"{safe_uid}.eml"
        try:
            file_path.write_bytes(raw)
        except OSError as e:
            raise RuntimeError(f"Failed to save email raw data to {file_path}: {e}") from e
        return file_path

    def read_raw(self, file_path: str | Path) -> bytes | None:
        p = Path(file_path)
        if not p.exists():
            return None
        try:
            return p.read_bytes()
        except OSError as e:
            logging.getLogger(__name__).warning("Failed to read %s: %s", p, e)
            return None

    def parse_email(self, raw: bytes) -> email.message.EmailMessage:
        return email.message_from_bytes(raw, policy=policy.default)

    def delete_raw(self, file_path: str | Path) -> bool:
        p = Path(file_path)
        if p.exists():
            try:
                p.unlink()
                return True
            except OSError as e:
                logging.getLogger(__name__).warning("Failed to delete %s: %s", p, e)
        return False

    def save_attachment(self, email_id: int, filename: str, data: bytes) -> Path:
        att_dir = self._attachment_dir(email_id)
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        file_path = att_dir / safe_name
        try:
            file_path.write_bytes(data)
        except OSError as e:
            raise RuntimeError(f"Failed to save attachment to {file_path}: {e}") from e
        return file_path

    def delete_attachments(self, email_id: int) -> None:
        att_dir = self._attachment_dir(email_id)
        if att_dir.exists():
            for f in att_dir.iterdir():
                try:
                    f.unlink()
                except OSError as e:
                    logging.getLogger(__name__).warning("Failed to delete attachment %s: %s", f, e)
            try:
                att_dir.rmdir()
            except OSError as e:
                logging.getLogger(__name__).warning("Failed to remove attachment dir %s: %s", att_dir, e)

    def delete_account_data(self, account_id: int) -> None:
        account_dir = self._account_dir(account_id)
        if account_dir.exists():
            for folder_dir in account_dir.iterdir():
                if folder_dir.is_dir():
                    for f in folder_dir.iterdir():
                        try:
                            f.unlink()
                        except OSError as e:
                            logging.getLogger(__name__).warning("Failed to delete %s: %s", f, e)
                    try:
                        folder_dir.rmdir()
                    except OSError as e:
                        logging.getLogger(__name__).warning("Failed to remove dir %s: %s", folder_dir, e)
            try:
                account_dir.rmdir()
            except OSError as e:
                logging.getLogger(__name__).warning("Failed to remove account dir %s: %s", account_dir, e)

    def cleanup_orphan_attachments(self) -> int:
        """Remove attachment directories with no matching email record.

        Returns:
            Number of orphan directories removed.
        """
        from openemail.storage.database import db

        removed = 0
        att_root = settings.attachment_dir
        if not att_root.exists():
            return removed

        for entry in att_root.iterdir():
            if not entry.is_dir():
                continue
            try:
                email_id = int(entry.name)
            except ValueError:
                continue

            row = db.fetchone("SELECT id FROM emails WHERE id = ?", (email_id,))
            if row is None:
                # No matching email — orphan
                for f in entry.iterdir():
                    f.unlink()
                entry.rmdir()
                removed += 1

        return removed


mail_store = MailStore()
