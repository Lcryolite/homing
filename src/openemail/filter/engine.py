from __future__ import annotations

from dataclasses import dataclass

from openemail.models.email import Email
from openemail.models.filter_rule import FilterRule
from openemail.models.folder import Folder
from openemail.models.tag import Tag
from openemail.storage.database import db

from .rule_matcher import RuleMatcher


@dataclass
class FilterResult:
    action: str  # none/move/tag/mark_read/delete/spam
    rule_name: str = ""
    target: str = ""


class FilterEngine:
    """过滤规则引擎"""

    _instance: "FilterEngine" | None = None

    def __new__(cls) -> "FilterEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._rules: list[FilterRule] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """从数据库加载所有启用的规则"""
        self._rules = FilterRule.get_all_enabled()

    def reload_rules(self) -> None:
        """重新加载规则"""
        self._load_rules()

    def apply(self, email: Email) -> FilterResult:
        """对邮件应用所有规则"""
        for rule in self._rules:
            if RuleMatcher.matches(rule, email):
                result = self._execute_rule(rule, email)
                if result.action != "none":
                    rule.increment_hit()
                    return result
        return FilterResult(action="none")

    def _execute_rule(self, rule: FilterRule, email: Email) -> FilterResult:
        """执行规则动作"""
        action = rule.action

        if action == "move_spam":
            email.mark_spam(f"规则：{rule.name}")
            spam_folder = Folder.get_by_name(email.account_id, "Spam")
            if spam_folder:
                email.move_to_folder(spam_folder.id)
            return FilterResult(action="spam", rule_name=rule.name)

        elif action == "move":
            # 移动到指定文件夹
            if rule.action_target:
                folder = Folder.get_by_name(email.account_id, rule.action_target)
                if folder:
                    email.move_to_folder(folder.id)
                    return FilterResult(
                        action="move", rule_name=rule.name, target=rule.action_target
                    )

        elif action == "tag":
            # 打标签
            if rule.action_target:
                tag = Tag.get_by_name(rule.action_target)
                if tag:
                    email.add_tag(tag)
                    return FilterResult(
                        action="tag", rule_name=rule.name, target=rule.action_target
                    )

        elif action == "mark_read":
            email.mark_read()
            return FilterResult(action="mark_read", rule_name=rule.name)

        elif action == "delete":
            email.is_deleted = True
            db.update("emails", {"is_deleted": 1}, "id = ?", (email.id,))
            return FilterResult(action="delete", rule_name=rule.name)

        return FilterResult(action="none")
