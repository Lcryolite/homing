from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QCoreApplication

logger = logging.getLogger(__name__)

_translator = None
_current_locale: Optional[str] = None


def tr(context: str, key: str, default: str = "") -> str:
    """
    翻译函数，为 i18n 打基础。

    Args:
        context: Qt 翻译上下文（通常是类名）
        key: 翻译键
        default: 默认文本（中文）

    Returns:
        翻译后的文本
    """
    if not default:
        default = key
    translated = QCoreApplication.translate(context, key)
    if translated == key and default:
        return default
    return translated


STRING_CATALOG = {
    "ComposeWindow": {
        "window_title_compose": "写邮件",
        "window_title_reply": "回复邮件",
        "window_title_forward": "转发邮件",
        "btn_send": "发送",
        "btn_sending": "发送中...",
        "btn_save_draft": "存草稿",
        "btn_cancel": "取消",
        "btn_add_attachment": "📎 添加附件",
        "label_from": "发件人:",
        "label_to": "收件人:",
        "label_cc": "抄送:",
        "label_subject": "主题:",
        "placeholder_to": "输入收件人地址，多个用逗号分隔",
        "placeholder_cc": "抄送地址，多个用逗号分隔",
        "placeholder_subject": "邮件主题",
        "placeholder_body": "在此输入邮件正文...",
        "tab_plain_text": "纯文本",
        "draft_saved": "草稿已保存",
        "draft_saved_local": "草稿已保存到本地",
        "draft_save_failed": "保存失败",
        "draft_save_failed_msg": "草稿保存失败，请重试",
        "send_failed": "发送失败",
        "send_failed_msg": "邮件发送失败，请稍后重试",
        "send_error": "发送错误",
        "format_error": "格式错误",
        "invalid_email": "邮箱地址格式错误: {}",
        "attachment_size_limit": "大小限制",
        "attachment_size_exceeded": "附件总大小已超过限制。",
    },
    "MailView": {
        "no_subject": "(无主题)",
        "label_from": "发件人: {}",
        "label_to": "收件人: {}",
        "spam_label": "垃圾邮件: {}",
    },
    "AccountDialog": {
        "title_add": "添加账户",
        "title_edit": "编辑账户",
    },
    "DesktopNotifier": {
        "new_mail": "新邮件: {}",
        "account": "账号: {}",
    },
}


def get_string(context: str, key: str, **kwargs) -> str:
    """
    获取本地化字符串。

    优先使用 Qt 翻译，回退到 STRING_CATALOG 中的默认值。

    Args:
        context: 上下文名称
        key: 字符串键
        **kwargs: 格式化参数

    Returns:
        本地化字符串
    """
    translated = QCoreApplication.translate(context, key)
    if translated != key:
        result = translated
    else:
        catalog = STRING_CATALOG.get(context, {})
        result = catalog.get(key, key)

    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return result


def load_translation(locale: str) -> bool:
    """
    加载翻译文件。

    Args:
        locale: 语言代码（如 'zh_CN', 'en_US'）

    Returns:
        是否加载成功
    """
    global _translator, _current_locale

    if locale == _current_locale:
        return True

    if _translator:
        QCoreApplication.removeTranslator(_translator)

    if locale in ("zh_CN", "zh", ""):
        _current_locale = locale
        _translator = None
        return True

    from PyQt6.QtCore import QTranslator

    translator = QTranslator()
    if translator.load(f"openemail_{locale}", ":/i18n"):
        QCoreApplication.installTranslator(translator)
        _translator = translator
        _current_locale = locale
        logger.info("Loaded translation: %s", locale)
        return True

    logger.warning("Translation not found: %s", locale)
    _current_locale = locale
    _translator = None
    return False
