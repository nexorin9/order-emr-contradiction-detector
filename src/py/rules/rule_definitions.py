"""
矛盾检测规则定义加载模块

提供RuleDefinitionsLoader类，
支持从YAML文件加载和解析矛盾检测规则。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class KeywordMatchingConfig:
    """关键词匹配配置"""

    fuzzy_match: bool = True
    synonyms: Dict[str, List[str]] = field(default_factory=dict)
    exclusion_keywords: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeywordMatchingConfig":
        """从字典创建配置对象"""
        return cls(
            fuzzy_match=data.get("fuzzy_match", True),
            synonyms=data.get("synonyms", {}),
            exclusion_keywords=data.get("exclusion_keywords", []),
        )


@dataclass
class TimeWindowConfig:
    """时间窗口配置"""

    minutes: int = 120
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeWindowConfig":
        """从字典创建配置对象"""
        return cls(
            minutes=data.get("minutes", 120),
            description=data.get("description", ""),
        )


@dataclass
class RuleDefinition:
    """单条矛盾检测规则定义"""

    rule_id: str
    rule_type: str
    display_name: str
    description: str
    severity: str
    required_his_fields: List[str]
    required_emr_fields: List[str]
    keyword_matching: KeywordMatchingConfig
    time_window: TimeWindowConfig
    applicable_departments: List[str] = field(default_factory=list)
    applicable_order_types: List[str] = field(default_factory=list)
    applicable_record_types: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleDefinition":
        """从字典创建规则定义对象"""
        return cls(
            rule_id=data.get("rule_id", ""),
            rule_type=data.get("rule_type", ""),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            severity=data.get("severity", "medium"),
            required_his_fields=data.get("required_his_fields", []),
            required_emr_fields=data.get("required_emr_fields", []),
            keyword_matching=KeywordMatchingConfig.from_dict(
                data.get("keyword_matching", {})
            ),
            time_window=TimeWindowConfig.from_dict(data.get("time_window", {})),
            applicable_departments=data.get("applicable_departments", []),
            applicable_order_types=data.get("applicable_order_types", []),
            applicable_record_types=data.get("applicable_record_types", []),
        )

    def is_applicable_department(self, department: str) -> bool:
        """检查科室是否适用此规则"""
        if not self.applicable_departments:
            return True  # 空列表表示所有科室适用
        return department in self.applicable_departments

    def is_applicable_order_type(self, order_type: str) -> bool:
        """检查医嘱类型是否适用此规则"""
        if not self.applicable_order_types:
            return True  # 空列表表示所有类型适用
        return order_type in self.applicable_order_types

    def is_applicable_record_type(self, record_type: str) -> bool:
        """检查记录类型是否适用此规则"""
        if not self.applicable_record_types:
            return True  # 空列表表示所有类型适用
        return record_type in self.applicable_record_types


@dataclass
class AlertThreshold:
    """告警阈值配置"""

    name: str
    threshold: int
    description: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertThreshold":
        """从字典创建告警阈值对象"""
        return cls(
            name=data.get("name", "info"),
            threshold=data.get("threshold", 0),
            description=data.get("description", ""),
        )


@dataclass
class AlertConfig:
    """告警配置"""

    doctor_daily_threshold: int = 3
    department_daily_threshold: int = 10
    high_severity_threshold: int = 1
    alert_levels: List[AlertThreshold] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertConfig":
        """从字典创建告警配置对象"""
        alert_levels = [
            AlertThreshold.from_dict(level)
            for level in data.get("alert_levels", [])
        ]
        return cls(
            doctor_daily_threshold=data.get("doctor_daily_threshold", 3),
            department_daily_threshold=data.get("department_daily_threshold", 10),
            high_severity_threshold=data.get("high_severity_threshold", 1),
            alert_levels=alert_levels,
        )

    def get_alert_level(self, count: int) -> str:
        """根据数量获取告警级别"""
        for level in sorted(self.alert_levels, key=lambda x: x.threshold, reverse=True):
            if count >= level.threshold:
                return level.name
        return "info"


@dataclass
class SeverityDefinition:
    """严重程度定义"""

    description: str
    examples: List[str]
    action: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeverityDefinition":
        """从字典创建严重程度定义对象"""
        return cls(
            description=data.get("description", ""),
            examples=data.get("examples", []),
            action=data.get("action", ""),
        )


@dataclass
class SeverityConfig:
    """严重程度配置"""

    high: SeverityDefinition
    medium: SeverityDefinition
    low: SeverityDefinition

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SeverityConfig":
        """从字典创建严重程度配置对象"""
        return cls(
            high=SeverityDefinition.from_dict(data.get("high", {})),
            medium=SeverityDefinition.from_dict(data.get("medium", {})),
            low=SeverityDefinition.from_dict(data.get("low", {})),
        )


class RuleDefinitionsLoader:
    """矛盾检测规则定义加载器

    支持从YAML文件加载规则定义，
    提供规则查询和管理功能。
    """

    def __init__(self, rules_file_path: Optional[str] = None):
        """初始化规则加载器

        Args:
            rules_file_path: 规则YAML文件路径，若为None则使用默认路径
        """
        self.rules_file_path = rules_file_path
        self._rules: Dict[str, RuleDefinition] = {}
        self._alert_config: Optional[AlertConfig] = None
        self._severity_config: Optional[SeverityConfig] = None
        self._version: str = ""

    def load(self, rules_file_path: Optional[str] = None) -> None:
        """加载规则定义文件

        Args:
            rules_file_path: 规则YAML文件路径

        Raises:
            FileNotFoundError: 规则文件不存在
            ValueError: 规则文件格式错误
        """
        if rules_file_path:
            self.rules_file_path = rules_file_path

        if not self.rules_file_path:
            raise ValueError("未指定规则文件路径")

        rules_path = Path(self.rules_file_path)
        if not rules_path.exists():
            raise FileNotFoundError(f"规则文件不存在: {rules_path}")

        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"规则文件为空: {rules_path}")

        # 解析版本
        self._version = data.get("version", "1.0")

        # 解析规则定义
        self._rules = {}
        rules_data = data.get("rules", {})
        for rule_name, rule_data in rules_data.items():
            if not isinstance(rule_data, dict):
                continue
            rule_def = RuleDefinition.from_dict(rule_data)
            self._rules[rule_def.rule_type] = rule_def
            logger.info(
                f"加载规则: {rule_def.rule_id} - {rule_def.display_name} "
                f"({rule_def.rule_type})"
            )

        # 解析告警配置
        alert_data = data.get("alert_thresholds", {})
        self._alert_config = AlertConfig.from_dict(alert_data)

        # 解析严重程度配置
        severity_data = data.get("severity_thresholds", {})
        self._severity_config = SeverityConfig.from_dict(severity_data)

        logger.info(f"共加载 {len(self._rules)} 条规则定义")

    def get_rule(self, rule_type: str) -> Optional[RuleDefinition]:
        """获取指定类型的规则定义

        Args:
            rule_type: 规则类型（如 ordered_but_not_recorded）

        Returns:
            规则定义对象，若不存在则返回None
        """
        return self._rules.get(rule_type)

    def get_all_rules(self) -> Dict[str, RuleDefinition]:
        """获取所有规则定义

        Returns:
            规则类型到规则定义对象的字典
        """
        return self._rules.copy()

    def get_rule_types(self) -> List[str]:
        """获取所有规则类型

        Returns:
            规则类型列表
        """
        return list(self._rules.keys())

    def get_alert_config(self) -> Optional[AlertConfig]:
        """获取告警配置

        Returns:
            告警配置对象
        """
        return self._alert_config

    def get_severity_config(self) -> Optional[SeverityConfig]:
        """获取严重程度配置

        Returns:
            严重程度配置对象
        """
        return self._severity_config

    def get_version(self) -> str:
        """获取规则文件版本

        Returns:
            版本字符串
        """
        return self._version

    def get_synonyms_for_item(self, item_name: str) -> List[str]:
        """获取项目名称的同义词列表

        Args:
            item_name: 项目名称（如 B超、血常规）

        Returns:
            包含原名称和所有同义词的列表
        """
        synonyms = [item_name]

        for rule_type, rule_def in self._rules.items():
            rule_synonyms = rule_def.keyword_matching.synonyms
            for key, values in rule_synonyms.items():
                if item_name == key:
                    synonyms.extend(values)
                elif item_name in values:
                    synonyms.append(key)
                    synonyms.extend(values)

        # 去重并保持顺序
        seen = set()
        result = []
        for s in synonyms:
            if s not in seen:
                seen.add(s)
                result.append(s)

        return result

    def is_exclusion_keyword(
        self, text: str, rule_type: Optional[str] = None
    ) -> bool:
        """检查文本中是否包含排除关键词

        Args:
            text: 待检查的文本
            rule_type: 规则类型，若为None则检查所有规则

        Returns:
            若包含排除关键词则返回True
        """
        if rule_type:
            rule_def = self._rules.get(rule_type)
            if rule_def:
                exclusions = rule_def.keyword_matching.exclusion_keywords
                return any(excl in text for excl in exclusions)
        else:
            for rule_def in self._rules.values():
                exclusions = rule_def.keyword_matching.exclusion_keywords
                if any(excl in text for excl in exclusions):
                    return True

        return False

    def get_time_window_minutes(self, rule_type: str) -> int:
        """获取指定规则的时间窗口分钟数

        Args:
            rule_type: 规则类型

        Returns:
            时间窗口分钟数，默认120分钟
        """
        rule_def = self._rules.get(rule_type)
        if rule_def:
            return rule_def.time_window.minutes
        return 120  # 默认值
