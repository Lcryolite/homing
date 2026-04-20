#!/usr/bin/env python3
"""
异常处理工具
"""

import sys
import traceback
import logging
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)


class OpenEmailException(Exception):
    """OpenEmail 应用基础异常"""

    code: str = "UNKNOWN_ERROR"
    message: str = "未知错误"

    def __init__(self, message: Optional[str] = None, **kwargs):
        self.message = message or self.message
        self.kwargs = kwargs
        super().__init__(self.message)


class AuthException(OpenEmailException):
    """认证相关异常"""

    code = "AUTH_FAILED"
    message = "认证失败"


class NetworkException(OpenEmailException):
    """网络相关异常"""

    code = "NETWORK_ERROR"
    message = "网络连接错误"


class ConfigException(OpenEmailException):
    """配置相关异常"""

    code = "CONFIG_ERROR"
    message = "配置错误"


class DatabaseException(OpenEmailException):
    """数据库相关异常"""

    code = "DATABASE_ERROR"
    message = "数据库操作失败"


class OAuthException(OpenEmailException):
    """OAuth 相关异常"""

    code = "OAUTH_ERROR"
    message = "OAuth 认证失败"


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """
    全局异常处理器
    """
    # 忽略 KeyboardInterrupt 以便正常退出
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # 记录异常到日志
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical("未捕获的异常:\n%s", error_msg)

    # 写入 crash.log
    try:
        import os

        data_dir = os.path.expanduser("~/.openemail")
        os.makedirs(data_dir, exist_ok=True)
        crash_log_file = os.path.join(data_dir, "crash.log")
        with open(crash_log_file, "a", encoding="utf-8") as f:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{'=' * 60}\n[{timestamp}] Uncaught Exception:\n")
            f.write(error_msg)
            f.write("\n")
    except Exception as log_exc:
        logger.error("写入 crash.log 失败: %s", str(log_exc))

    # 调用原始异常处理器
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def install_global_handler():
    """安装全局异常处理器"""
    sys.excepthook = global_exception_handler


def catch_and_log(func):
    """
    装饰器：捕获异常并记录日志

    Args:
        func: 函数或方法
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 记录异常
            error_msg = (
                f"函数 {func.__name__} 执行失败: {str(e)}\n{traceback.format_exc()}"
            )
            logger.error(error_msg)

            # 重新抛出异常，让调用者处理
            raise

    return wrapper


def safe_execute(default_value=None, log_exception=True):
    """
    安全执行装饰器，异常时返回默认值

    Args:
        default_value: 异常时返回的默认值
        log_exception: 是否记录异常日志
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_exception:
                    logger.warning("安全执行失败: %s - %s", func.__name__, str(e))
                return default_value

        return wrapper

    return decorator


def detect_last_crash() -> bool:
    """
    检测上次是否异常退出

    Returns:
        bool: 如果检测到上次异常退出返回 True
    """
    try:
        import os

        data_dir = os.path.expanduser("~/.openemail")
        crash_log_file = os.path.join(data_dir, "crash.log")

        if not os.path.exists(crash_log_file):
            return False

        # 检查文件最后修改时间
        import datetime

        mtime = os.path.getmtime(crash_log_file)
        now = datetime.datetime.now().timestamp()

        # 如果最后崩溃发生在最近24小时内
        return (now - mtime) < 86400
    except Exception:
        return False


def clear_crash_flag():
    """清除崩溃标志（通常在应用正常退出时调用）"""
    try:
        import os

        data_dir = os.path.expanduser("~/.openemail")
        crash_log_file = os.path.join(data_dir, "crash.log")

        if os.path.exists(crash_log_file):
            # 重命名为归档
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = os.path.join(data_dir, f"crash_{timestamp}.log")
            os.rename(crash_log_file, archive_file)
    except Exception as e:
        logger.warning("清除崩溃标志失败: %s", str(e))
