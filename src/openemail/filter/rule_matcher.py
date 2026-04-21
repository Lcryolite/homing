from __future__ import annotations

import re

from openemail.models.email import Email
from openemail.models.filter_rule import FilterRule, MatchField, RuleType


class RuleMatcher:
    """规则匹配器"""

    @staticmethod
    def matches(rule: FilterRule, email: Email) -> bool:
        """检查邮件是否匹配规则"""
        if rule.rule_type == RuleType.KEYWORD.value:
            return RuleMatcher._match_keyword(rule, email)
        elif rule.rule_type == RuleType.REGEX.value:
            return RuleMatcher._match_regex(rule, email)
        elif rule.rule_type == RuleType.BLACKLIST_SENDER.value:
            return RuleMatcher._match_blacklist_sender(rule, email)
        elif rule.rule_type == RuleType.BLACKLIST_DOMAIN.value:
            return RuleMatcher._match_blacklist_domain(rule, email)
        return False

    @staticmethod
    def _match_keyword(rule: FilterRule, email: Email) -> bool:
        """关键词匹配"""
        pattern = rule.pattern.lower()
        match_field = rule.match_field

        if (
            match_field == MatchField.SUBJECT.value
            or match_field == MatchField.ALL.value
        ):
            if pattern in (email.subject or "").lower():
                return True

        if (
            match_field == MatchField.SENDER.value
            or match_field == MatchField.ALL.value
        ):
            if pattern in (email.sender_name or "").lower():
                return True
            if pattern in (email.sender_addr or "").lower():
                return True

        if match_field == MatchField.BODY.value or match_field == MatchField.ALL.value:
            if pattern in (email.preview_text or "").lower():
                return True

        return False

    @staticmethod
    def _match_regex(rule: FilterRule, email: Email) -> bool:
        """正则表达式匹配"""
        try:
            regex = re.compile(rule.pattern, re.IGNORECASE)
            match_field = rule.match_field

            if (
                match_field == MatchField.SUBJECT.value
                or match_field == MatchField.ALL.value
            ):
                if regex.search(email.subject or ""):
                    return True

            if (
                match_field == MatchField.SENDER.value
                or match_field == MatchField.ALL.value
            ):
                if regex.search(email.sender_name or "") or regex.search(
                    email.sender_addr or ""
                ):
                    return True

            if (
                match_field == MatchField.BODY.value
                or match_field == MatchField.ALL.value
            ):
                if regex.search(email.preview_text or ""):
                    return True

            return False
        except re.error:
            return False

    @staticmethod
    def _match_blacklist_sender(rule: FilterRule, email: Email) -> bool:
        """发件人黑名单匹配"""
        pattern = rule.pattern.lower()
        sender = email.sender_addr.lower()
        return pattern == sender or pattern in sender

    @staticmethod
    def _match_blacklist_domain(rule: FilterRule, email: Email) -> bool:
        """域名黑名单匹配"""
        pattern = rule.pattern.lower()
        sender = email.sender_addr.lower()
        if "@" in sender:
            domain = sender.split("@")[1]
            return pattern == domain or pattern in domain
        return False
