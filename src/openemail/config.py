import json
import os
import logging
from pathlib import Path
from typing import Any, Optional

_APP_NAME = "openemail"

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "system",
    "sync_interval_minutes": 5,
    "onboarding_state": "not_started",
    "window": {
        "width": 1200,
        "height": 800,
        "x": -1,
        "y": -1,
        "sidebar_width": 220,
        "detail_visible": True,
    },
    "accounts": [],
    "calendar_sync_enabled": False,
    "todo_sync_enabled": False,
    "semantic_search_enabled": False,
}


def _xdg_config_home() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base)
    return Path.home() / ".config"


def _xdg_data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base)
    return Path.home() / ".local" / "share"


def _xdg_cache_home() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base)
    return Path.home() / ".cache"


class Settings:
    def __init__(self) -> None:
        self._config_dir = _xdg_config_home() / _APP_NAME
        self._data_dir = _xdg_data_home() / _APP_NAME
        self._cache_dir = _xdg_cache_home() / _APP_NAME
        self._mail_dir = self._data_dir / "mail"
        self._attachment_dir = self._data_dir / "attachments"
        self._settings_file = self._config_dir / "settings.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        self._ensure_dirs()
        if self._settings_file.exists():
            try:
                text = self._settings_file.read_text(encoding="utf-8")
                self._data = json.loads(text)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        merged = {**_DEFAULT_SETTINGS, **self._data}
        for key, value in _DEFAULT_SETTINGS.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**value, **merged[key]}
        self._data = merged

    def _ensure_dirs(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._mail_dir.mkdir(parents=True, exist_ok=True)
        self._attachment_dir.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self._ensure_dirs()
        tmp = self._settings_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp.replace(self._settings_file)

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    @property
    def mail_dir(self) -> Path:
        return self._mail_dir

    @property
    def attachment_dir(self) -> Path:
        return self._attachment_dir

    @property
    def db_path(self) -> Path:
        return self._data_dir / "openemail.db"

    @property
    def oauth_creds_path(self) -> Path:
        """获取OAuth认证凭据文件路径"""
        return self._config_dir / "oauth_creds.json"

    def get_oauth_config(self) -> Optional[dict[str, dict[str, str]]]:
        """获取OAuth配置"""
        creds_path = self.oauth_creds_path
        if not creds_path.exists():
            logger.warning("OAuth配置文件不存在: %s", creds_path)
            return None

        try:
            content = creds_path.read_text(encoding="utf-8")
            config = json.loads(content)

            # 验证配置结构
            if not isinstance(config, dict):
                logger.error("OAuth配置格式错误: 应为字典")
                return None

            return config
        except json.JSONDecodeError as e:
            logger.error("OAuth配置JSON解析失败: %s", str(e))
            return None
        except Exception as e:
            logger.error("读取OAuth配置失败: %s", str(e))
            return None

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        obj = self._data
        for k in keys:
            if isinstance(obj, dict) and k in obj:
                obj = obj[k]
            else:
                return default
        return obj

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        obj = self._data
        for k in keys[:-1]:
            if k not in obj or not isinstance(obj[k], dict):
                obj[k] = {}
            obj = obj[k]
        obj[keys[-1]] = value
        self.save()

    @property
    def theme(self) -> str:
        return self._data.get("theme", "system")

    @theme.setter
    def theme(self, value: str) -> None:
        self._data["theme"] = value
        self.save()

    @property
    def sync_interval(self) -> int:
        return self._data.get("sync_interval_minutes", 5)

    @property
    def window_geometry(self) -> dict[str, int]:
        return self._data.get("window", {})

    @property
    def onboarding_state(self) -> str:
        """获取初始化引导状态"""
        return self._data.get("onboarding_state", "not_started")

    @onboarding_state.setter
    def onboarding_state(self, value: str) -> None:
        """设置初始化引导状态"""
        self._data["onboarding_state"] = value
        self.save()

    def save_window_geometry(
        self, x: int, y: int, w: int, h: int, sidebar_w: int
    ) -> None:
        self._data["window"] = {
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "sidebar_width": sidebar_w,
            "detail_visible": self._data.get("window", {}).get("detail_visible", True),
        }
        self.save()


settings = Settings()
