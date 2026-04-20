from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple

from openemail.models.email import Email
from openemail.models.filter_rule import FilterRule
from openemail.models.folder import Folder

from openemail.models.label import Label
from openemail.models.contact import Contact
from openemail.storage.database import db

logger = logging.getLogger(__name__)


class EnhancedRuleType(Enum):
    """增强版规则类型"""

    KEYWORD = "keyword"
    REGEX = "regex"
    SENDER_OR_DOMAIN = "sender_or_domain"
    SENDER_IN_CONTACTS = "sender_in_contacts"
    HAS_ATTACHMENT = "has_attachment"
    SIZE_RANGE = "size_range"
    DATE_RANGE = "date_range"
    AI_CLASSIFICATION = "ai_classification"


class EnhancedFilterAction(Enum):
    """增强版过滤器动作"""

    MOVE_TO_FOLDER = "move_to_folder"
    APPLY_LABEL = "apply_label"
    MARK_READ = "mark_read"
    MARK_IMPORTANT = "mark_important"
    SET_FLAG = "set_flag"
    DELETE = "delete"
    MARK_SPAM = "mark_spam"
    FORWARD = "forward"
    SEND_RESPONSE = "send_response"
    NOTIFY = "notify"
    RUN_SCRIPT = "run_script"


class FilterCondition(Enum):
    """过滤条件关系"""

    AND = "and"
    OR = "or"
    NOT = "not"


@dataclass
class EnhancedFilterRule:
    """增强版过滤规则"""

    id: int = 0
    name: str = ""
    description: str = ""
    rule_type: str = "keyword"
    conditions: List[Dict] = None
    condition_logic: str = "and"
    is_enabled: bool = True
    priority: int = 0
    actions: List[Dict] = None
    stop_processing: bool = False
    apply_to_existing: bool = False
    last_triggered: Optional[datetime] = None
    hit_count: int = 0
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None

    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []
        if self.actions is None:
            self.actions = []
        if self.creation_date is None:
            self.creation_date = datetime.now()

    def save(self) -> int:
        """保存规则到数据库"""
        data = {
            "name": self.name,
            "description": self.description or "",
            "rule_type": self.rule_type,
            "conditions": json.dumps(self.conditions, ensure_ascii=False),
            "condition_logic": self.condition_logic,
            "is_enabled": int(self.is_enabled),
            "priority": self.priority,
            "actions": json.dumps(self.actions, ensure_ascii=False),
            "stop_processing": int(self.stop_processing),
            "apply_to_existing": int(self.apply_to_existing),
            "last_triggered": self.last_triggered.isoformat()
            if self.last_triggered
            else None,
            "hit_count": self.hit_count,
            "creation_date": self.creation_date.isoformat(),
            "modification_date": datetime.now().isoformat(),
        }

        if self.id == 0:
            self.id = db.insert("enhanced_filter_rules", data)
        else:
            db.update("enhanced_filter_rules", data, "id = ?", (self.id,))
            self.modification_date = datetime.now()

        return self.id

    def delete(self) -> None:
        """删除规则"""
        if self.id:
            db.delete("enhanced_filter_rules", "id = ?", (self.id,))
            self.id = 0

    def increment_hit(self) -> None:
        """增加触发计数"""
        self.hit_count += 1
        self.last_triggered = datetime.now()
        db.update(
            "enhanced_filter_rules",
            {
                "hit_count": self.hit_count,
                "last_triggered": self.last_triggered.isoformat(),
            },
            "id = ?",
            (self.id,),
        )

    def matches_email(self, email: Email) -> bool:
        """检查邮件是否匹配规则"""
        if not self.conditions:
            return False

        # 根据逻辑关系评估条件
        if self.condition_logic == "and":
            return all(
                self._evaluate_condition(cond, email) for cond in self.conditions
            )
        elif self.condition_logic == "or":
            return any(
                self._evaluate_condition(cond, email) for cond in self.conditions
            )
        else:
            return False

    def _evaluate_condition(self, condition: Dict, email: Email) -> bool:
        """评估单个条件"""
        condition_type = condition.get("type")
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        if not condition_type or not field:
            return False

        try:
            if condition_type == "keyword":
                return self._evaluate_keyword(field, operator, value, email)
            elif condition_type == "regex":
                return self._evaluate_regex(field, operator, value, email)
            elif condition_type == "sender":
                return self._evaluate_sender(field, operator, value, email)
            elif condition_type == "date":
                return self._evaluate_date(field, operator, value, email)
            elif condition_type == "size":
                return self._evaluate_size(field, operator, value, email)
            elif condition_type == "flag":
                return self._evaluate_flag(field, operator, value, email)
            elif condition_type == "attachment":
                return self._evaluate_attachment(field, operator, value, email)
            else:
                return False
        except Exception:
            return False

    def _evaluate_keyword(
        self, field: str, operator: str, value: str, email: Email
    ) -> bool:
        """评估关键词条件"""
        email_value = self._get_email_field(field, email)
        if not email_value:
            return False

        if operator == "contains":
            return value.lower() in email_value.lower()
        elif operator == "not_contains":
            return value.lower() not in email_value.lower()
        elif operator == "equals":
            return email_value.lower() == value.lower()
        elif operator == "starts_with":
            return email_value.lower().startswith(value.lower())
        elif operator == "ends_with":
            return email_value.lower().endswith(value.lower())
        else:
            return False

    def _evaluate_regex(
        self, field: str, operator: str, pattern: str, email: Email
    ) -> bool:
        """评估正则表达式条件"""
        email_value = self._get_email_field(field, email)
        if not email_value:
            return False

        try:
            if operator == "matches":
                return bool(re.search(pattern, email_value, re.IGNORECASE))
            elif operator == "not_matches":
                return not bool(re.search(pattern, email_value, re.IGNORECASE))
            else:
                return False
        except re.error:
            return False

    def _evaluate_sender(
        self, field: str, operator: str, value: str, email: Email
    ) -> bool:
        """评估发件人条件"""
        sender = email.sender_addr.lower()
        value_lower = value.lower()

        if operator == "equals":
            return sender == value_lower
        elif operator == "contains":
            return value_lower in sender
        elif operator == "domain":
            # 提取域名
            if "@" in value_lower:
                # 已经是完整的域名
                return (
                    sender.endswith("@" + value_lower) if "@" in value_lower else False
                )
            else:
                # 只有域名部分
                return sender.endswith("@" + value_lower)
        elif operator == "in_contacts":
            # 检查是否在联系人中
            return Contact.exists_with_email(email.sender_addr)
        else:
            return False

    def _evaluate_date(
        self, field: str, operator: str, value: str, email: Email
    ) -> bool:
        """评估日期条件"""
        if not email.date:
            return False

        email_date = email.date
        try:
            if operator == "older_than":
                days = int(value)
                return email_date < datetime.now() - timedelta(days=days)
            elif operator == "newer_than":
                days = int(value)
                return email_date > datetime.now() - timedelta(days=days)
            elif operator == "on_date":
                target_date = datetime.fromisoformat(value)
                return email_date.date() == target_date.date()
            elif operator == "before":
                target_date = datetime.fromisoformat(value)
                return email_date < target_date
            elif operator == "after":
                target_date = datetime.fromisoformat(value)
                return email_date > target_date
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _evaluate_size(
        self, field: str, operator: str, value: str, email: Email
    ) -> bool:
        """评估大小条件"""
        # 模拟邮件大小（实际项目中需要存储邮件大小）
        # 这里使用正文长度作为示例
        if not email.body:
            return False

        email_size = len(email.body)
        try:
            size_limit = int(value) * 1024  # 假设value是以KB为单位

            if operator == "greater_than":
                return email_size > size_limit
            elif operator == "less_than":
                return email_size < size_limit
            elif operator == "between":
                # value应该包含两个数字，用逗号分隔
                parts = value.split(",")
                if len(parts) != 2:
                    return False
                min_size = int(parts[0].strip()) * 1024
                max_size = int(parts[1].strip()) * 1024
                return min_size <= email_size <= max_size
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _evaluate_flag(
        self, field: str, operator: str, value: str, email: Email
    ) -> bool:
        """评估标记条件"""
        if field == "is_read":
            email_value = email.is_read == 1
        elif field == "is_flagged":
            email_value = email.is_flagged == 1
        elif field == "has_attachment":
            email_value = email.has_attachment == 1
        elif field == "is_spam":
            email_value = email.is_spam == 1
        else:
            return False

        expected_value = value.lower() == "true"

        if operator == "equals":
            return email_value == expected_value
        else:
            return False

    def _evaluate_attachment(
        self, field: str, operator: str, value: str, email: Email
    ) -> bool:
        """评估附件条件"""
        if not hasattr(email, "has_attachment") or not email.has_attachment:
            return False

        # 简化版本：只检查是否有附件
        if operator == "has":
            return email.has_attachment == 1
        elif operator == "has_not":
            return email.has_attachment == 0
        else:
            return False

    def _get_email_field(self, field: str, email: Email) -> str:
        """获取邮件字段值"""
        if field == "subject":
            return email.subject or ""
        elif field == "sender":
            return email.sender_addr or ""
        elif field == "sender_name":
            return email.sender_name or ""
        elif field == "to":
            return email.to_addrs or ""
        elif field == "body":
            return email.body or ""
        elif field == "preview":
            return email.preview_text or ""
        else:
            return ""

    def apply_actions(self, email: Email) -> bool:
        """应用规则动作"""
        if not self.actions:
            return False

        applied = False
        for action in self.actions:
            try:
                if self._apply_single_action(action, email):
                    applied = True
            except Exception as e:
                logger.error("应用动作时出错: %s", e)

        if applied:
            self.increment_hit()

        return applied

    def _apply_single_action(self, action: Dict, email: Email) -> bool:
        """应用单个动作"""
        action_type = action.get("type")
        target = action.get("target")

        if not action_type:
            return False

        try:
            if action_type == "move_to_folder":
                if target:
                    # 查找文件夹并移动
                    folder = Folder.get_by_name(email.account_id, target)
                    if folder:
                        email.move_to_folder(folder.id)
                        return True

            elif action_type == "apply_label":
                if target:
                    # 查找或创建标签并应用
                    label = Label.get_by_name(target, email.account_id)
                    if not label:
                        # 创建新标签
                        label = Label(
                            name=target,
                            display_name=target,
                            account_id=email.account_id,
                        )
                        label.save()

                    # 将标签应用到邮件
                    label.add_to_email(email.id)

            elif action_type == "mark_read":
                if not email.is_read:
                    email.mark_read()
                    return True

            elif action_type == "mark_important":
                # 标记为重要
                from openemail.storage.database import db

                db.update("emails", {"is_important": 1}, "id = ?", (email.id,))
                return True

            elif action_type == "set_flag":
                # 设置标记
                from openemail.storage.database import db

                flag_value = 1 if target.lower() == "true" else 0
                db.update("emails", {"is_flagged": flag_value}, "id = ?", (email.id,))
                email.is_flagged = flag_value
                return True

            elif action_type == "delete":
                email.is_deleted = True
                from openemail.storage.database import db

                db.update("emails", {"is_deleted": 1}, "id = ?", (email.id,))
                return True

            elif action_type == "mark_spam":
                email.mark_spam("过滤规则触发")
                spam_folder = Folder.get_by_name(email.account_id, "Spam")
                if spam_folder:
                    email.move_to_folder(spam_folder.id)
                return True

            else:
                return False
        except Exception:
            return False

    @classmethod
    def create_keyword_rule(
        cls,
        name: str,
        keywords: List[str],
        field: str = "all",
        actions: List[Dict] = None,
        priority: int = 0,
    ) -> EnhancedFilterRule:
        """创建关键词规则"""
        conditions = []
        for keyword in keywords:
            conditions.append(
                {
                    "type": "keyword",
                    "field": field,
                    "operator": "contains",
                    "value": keyword,
                }
            )

        if not actions:
            actions = [{"type": "move_to_folder", "target": "Spam"}]

        return cls(
            name=name,
            conditions=conditions,
            condition_logic="or",
            priority=priority,
            actions=actions,
        )

    @classmethod
    def create_sender_rule(
        cls,
        name: str,
        sender: str,
        is_blacklist: bool = True,
        actions: List[Dict] = None,
    ) -> EnhancedFilterRule:
        """创建发件人规则"""
        condition_type = "sender"

        # 检查是邮箱还是域名
        if "@" in sender:
            operator = "equals"
        else:
            operator = "domain"

        conditions = [
            {
                "type": condition_type,
                "field": "sender",
                "operator": operator,
                "value": sender,
            }
        ]

        if not actions:
            if is_blacklist:
                actions = [{"type": "move_to_folder", "target": "Spam"}]
            else:
                actions = [{"type": "mark_important", "target": ""}]

        return cls(
            name=name, conditions=conditions, condition_logic="and", actions=actions
        )

    @classmethod
    def get_by_id(cls, rule_id: int) -> EnhancedFilterRule | None:
        """根据ID获取规则"""
        row = db.fetchone(
            "SELECT * FROM enhanced_filter_rules WHERE id = ?", (rule_id,)
        )
        if row is None:
            return None
        return cls._from_row(row)

    @classmethod
    def get_all_enabled(cls) -> List[EnhancedFilterRule]:
        """获取所有已启用的规则"""
        rows = db.fetchall(
            "SELECT * FROM enhanced_filter_rules WHERE is_enabled = 1 ORDER BY priority DESC, hit_count DESC"
        )
        return [cls._from_row(r) for r in rows]

    @classmethod
    def get_all(cls) -> List[EnhancedFilterRule]:
        """获取所有规则"""
        rows = db.fetchall("SELECT * FROM enhanced_filter_rules ORDER BY priority DESC")
        return [cls._from_row(r) for r in rows]

    @classmethod
    def _from_row(cls, row: dict) -> FilterRule:
        """从数据库行创建规则对象"""

        # Helper function to mimic dict.get() behavior with sqlite3.Row
        def row_get(key, default=None):
            if key in row.keys():
                value = row[key]
                return default if value is None else value
            return default

        # 解析JSON字段
        conditions = (
            json.loads(row["conditions"])
            if "conditions" in row.keys() and row["conditions"]
            else []
        )
        actions = (
            json.loads(row["actions"])
            if "actions" in row.keys() and row["actions"]
            else []
        )

        # 解析日期字段
        def parse_date(date_str):
            if date_str:
                try:
                    return datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    return None
            return None

        return cls(
            id=row["id"],
            name=row["name"],
            description=row_get("description", ""),
            rule_type=row["rule_type"],
            conditions=conditions,
            condition_logic=row_get("condition_logic", "and"),
            is_enabled=bool(row["is_enabled"]),
            priority=row_get("priority", 0),
            actions=actions,
            stop_processing=bool(row_get("stop_processing", 0)),
            apply_to_existing=bool(row_get("apply_to_existing", 0)),
            last_triggered=parse_date(row_get("last_triggered")),
            hit_count=row_get("hit_count", 0),
            creation_date=parse_date(row_get("creation_date")),
            modification_date=parse_date(row_get("modification_date")),
        )
        actions = (
            json.loads(row["actions"])
            if "actions" in row.keys() and row["actions"]
            else []
        )

        # 解析日期字段
        def parse_date(date_str):
            if date_str:
                try:
                    return datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    return None
            return None

        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"] if "description" in row.keys() else "",
            rule_type=row["rule_type"],
            conditions=conditions,
            condition_logic=row["condition_logic"]
            if "condition_logic" in row.keys()
            else "and",
            is_enabled=bool(row["is_enabled"]),
            priority=row["priority"] if "priority" in row.keys() else 0,
            actions=actions,
            stop_processing=bool(
                row["stop_processing"] if "stop_processing" in row.keys() else 0
            ),
            apply_to_existing=bool(
                row["apply_to_existing"] if "apply_to_existing" in row.keys() else 0
            ),
            last_triggered=parse_date(
                row["last_triggered"] if "last_triggered" in row.keys() else None
            ),
            hit_count=row["hit_count"] if "hit_count" in row.keys() else 0,
            creation_date=parse_date(
                row["creation_date"] if "creation_date" in row.keys() else None
            ),
            modification_date=parse_date(
                row["modification_date"] if "modification_date" in row.keys() else None
            ),
        )


class EnhancedFilterEngine:
    """增强版过滤器引擎"""

    def __init__(self):
        self.rules: List[EnhancedFilterRule] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """加载规则"""
        self.rules = EnhancedFilterRule.get_all_enabled()

    def process_email(self, email: Email) -> bool:
        """处理邮件，应用匹配的规则"""
        if not email:
            return False

        rules_applied = 0

        for rule in self.rules:
            if rule.matches_email(email):
                if rule.apply_actions(email):
                    rules_applied += 1

                    # 如果规则设置了停止处理，则中断
                    if rule.stop_processing:
                        break

        return rules_applied > 0

    def process_batch(self, emails: List[Email]) -> Dict[str, Any]:
        """批量处理邮件"""
        results = {
            "total": len(emails),
            "processed": 0,
            "rules_applied": 0,
            "errors": [],
        }

        for email in emails:
            try:
                if self.process_email(email):
                    results["rules_applied"] += 1
                results["processed"] += 1
            except Exception as e:
                results["errors"].append(f"处理邮件 {email.id} 时出错: {e}")

        return results

    def create_rule_from_template(
        self, template_name: str, **kwargs
    ) -> EnhancedFilterRule:
        """从模板创建规则"""
        templates = {
            "newsletter": {
                "name": "新闻简报",
                "conditions": [
                    {
                        "type": "keyword",
                        "field": "subject",
                        "operator": "contains",
                        "value": "newsletter",
                    },
                    {
                        "type": "keyword",
                        "field": "subject",
                        "operator": "contains",
                        "value": "订阅",
                    },
                ],
                "actions": [{"type": "apply_label", "target": "新闻简报"}],
            },
            "notification": {
                "name": "系统通知",
                "conditions": [
                    {
                        "type": "keyword",
                        "field": "subject",
                        "operator": "contains",
                        "value": "notification",
                    },
                    {
                        "type": "keyword",
                        "field": "subject",
                        "operator": "contains",
                        "value": "通知",
                    },
                ],
                "actions": [{"type": "mark_read", "target": ""}],
            },
            "social_media": {
                "name": "社交媒体",
                "conditions": [
                    {
                        "type": "sender",
                        "field": "sender",
                        "operator": "domain",
                        "value": kwargs.get("domain", "facebook.com"),
                    }
                ],
                "actions": [{"type": "apply_label", "target": "社交媒体"}],
            },
        }

        if template_name not in templates:
            raise ValueError(f"模板 '{template_name}' 不存在")

        template = templates[template_name]

        return EnhancedFilterRule(
            name=kwargs.get("name", template["name"]),
            conditions=kwargs.get("conditions", template["conditions"]),
            actions=kwargs.get("actions", template["actions"]),
            condition_logic=kwargs.get("condition_logic", "or"),
            priority=kwargs.get("priority", 0),
        )

    def import_rules_from_file(self, file_path: str) -> List[EnhancedFilterRule]:
        """从文件导入规则"""
        # TODO: 实现从JSON文件导入规则
        return []

    def export_rules_to_file(self, file_path: str) -> bool:
        """导出规则到文件"""
        # TODO: 实现导出规则到JSON文件
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取过滤器统计信息"""
        try:
            rows = db.fetchall("""
                SELECT 
                    COUNT(*) as total_rules,
                    SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) as enabled_rules,
                    SUM(hit_count) as total_hits,
                    AVG(priority) as avg_priority,
                    MAX(last_triggered) as last_triggered_date
                FROM enhanced_filter_rules
            """)

            if not rows:
                return {}

            return {
                "total_rules": rows[0]["total_rules"] or 0,
                "enabled_rules": rows[0]["enabled_rules"] or 0,
                "total_hits": rows[0]["total_hits"] or 0,
                "avg_priority": rows[0]["avg_priority"] or 0,
                "last_triggered": rows[0]["last_triggered_date"],
            }
        except Exception:
            return {}

    def test_rule_on_email(self, rule_id: int, email: Email) -> Dict[str, Any]:
        """测试规则在指定邮件上的匹配情况"""
        rule = EnhancedFilterRule.get_by_id(rule_id)
        if not rule:
            return {"error": "规则不存在"}

        results = {"rule_matched": False, "conditions": [], "would_apply_actions": []}

        # 测试每个条件
        for i, condition in enumerate(rule.conditions):
            matched = rule._evaluate_condition(condition, email)
            results["conditions"].append(
                {"index": i, "condition": condition, "matched": matched}
            )

        # 检查整体匹配
        results["rule_matched"] = rule.matches_email(email)

        # 如果匹配，列出将应用的动作
        if results["rule_matched"]:
            results["would_apply_actions"] = rule.actions

        return results


def init_enhanced_filter_engine() -> None:
    """初始化增强过滤器引擎"""
    # 创建表
    db.execute("""
        CREATE TABLE IF NOT EXISTS enhanced_filter_rules (
            id                INTEGER PRIMARY KEY,
            name              TEXT NOT NULL,
            description       TEXT,
            rule_type         TEXT NOT NULL DEFAULT 'keyword',
            conditions        TEXT NOT NULL,
            condition_logic   TEXT NOT NULL DEFAULT 'and',
            is_enabled        INTEGER NOT NULL DEFAULT 1,
            priority          INTEGER NOT NULL DEFAULT 0,
            actions           TEXT NOT NULL,
            stop_processing   INTEGER NOT NULL DEFAULT 0,
            apply_to_existing INTEGER NOT NULL DEFAULT 0,
            last_triggered    TEXT,
            hit_count         INTEGER NOT NULL DEFAULT 0,
            creation_date     TEXT NOT NULL,
            modification_date TEXT NOT NULL
        )
    """)

    # 创建索引
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_enhanced_filter_enabled ON enhanced_filter_rules(is_enabled, priority)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_enhanced_filter_hits ON enhanced_filter_rules(hit_count DESC)"
    )

    logger.info("增强版过滤器引擎初始化完成")


# 自动初始化
init_enhanced_filter_engine()
